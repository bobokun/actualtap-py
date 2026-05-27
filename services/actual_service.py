import hashlib
import json
from collections import OrderedDict
from decimal import ROUND_CEILING
from decimal import ROUND_HALF_UP
from decimal import Decimal
from typing import List

from actual import Actual
from actual.database import Transactions
from actual.queries import create_transaction
from actual.queries import get_payees
from actual.queries import get_ruleset
from sqlalchemy import func
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlmodel import col
from sqlmodel import select

from core.config import AccountMapping
from core.config import settings
from core.logs import MyLogger
from core.util import convert_to_date
from schemas.transactions import Transaction

logger = MyLogger()

CENTS = Decimal("0.01")


def apply_topup(amount: Decimal, topup: int):
    """Apply a Trade-Republic-style top-up to a spend amount.

    The card is "topped up" in whole euros, so the amount actually leaving
    the account is rounded up to the next euro, and the rounding remainder
    is multiplied by the ``topup`` factor::

        remainder = ceil(|amount|) - |amount|
        if remainder > 0:  total = |amount| + topup * remainder
        else (whole euro): total = |amount| + topup

    Examples (topup = 1): 1.00 -> 2.00, 1.20 -> 2.00, 2.30 -> 3.00.
    Examples (topup = 2): 1.00 -> 3.00, 1.20 -> 2.80, 2.30 -> 3.70.

    The sign of ``amount`` is preserved (spends arrive negative). Returns a
    ``(new_amount, note_suffix)`` tuple; ``note_suffix`` is empty when no
    top-up was applied.
    """
    if not topup or topup <= 0:
        return amount, ""

    sign = Decimal(-1) if amount < 0 else Decimal(1)
    base = abs(amount)
    ceiled = base.to_integral_value(rounding=ROUND_CEILING)
    remainder = ceiled - base

    if remainder > 0:
        total = base + (Decimal(topup) * remainder)
    else:
        total = base + Decimal(topup)

    total = total.quantize(CENTS, rounding=ROUND_HALF_UP)
    new_amount = sign * total

    note_suffix = f"[topup {topup}x: orig {base.quantize(CENTS)} -> {total}]"
    return new_amount, note_suffix


class ActualService:
    def __init__(self):
        self.client = None

    @staticmethod
    def _build_import_id(account_id: str, amount: Decimal, date, payee: str, cleared: bool) -> str:
        normalized_amount = format(amount.normalize(), "f")
        normalized_payee = (payee or "").strip().lower()
        cleared_flag = "1" if cleared else "0"
        raw_key = json.dumps(
            [
                account_id,
                normalized_amount,
                date.isoformat(),
                normalized_payee,
                cleared_flag,
            ],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"ID-{digest}"

    @staticmethod
    def _is_duplicate_payee_error(error: Exception) -> bool:
        return isinstance(error, MultipleResultsFound) or "Multiple rows were found when one or none was required" in str(error)

    @staticmethod
    def _get_first_matching_payee(session, payee_name: str):
        matching_payees = get_payees(session, name=payee_name)
        if not matching_payees:
            return None
        return matching_payees[0]

    @staticmethod
    def _find_existing_by_imported_id(session, account_id: str, imported_id: str):
        # Strict imported_id dedup, scoped to the account and excluding
        # tombstoned rows. We deliberately avoid actualpy's reconcile fuzzy
        # match (±7 days same amount) because identical repeated spends
        # (e.g. same daily coffee) would otherwise collapse into one.
        query = select(Transactions).where(
            Transactions.acct == account_id,
            col(Transactions.financial_id) == imported_id,
            func.coalesce(Transactions.tombstone, 0) == 0,
        )
        return session.exec(query).first()

    @staticmethod
    def _unpack_mapping(value):
        """Return ``(account_id, topup)`` from any supported mapping value.

        Handles plain UUID strings (legacy), ``AccountMapping`` objects and
        raw dicts (used by some tests that assign settings directly).
        """
        if value is None:
            return None, 0
        if isinstance(value, str):
            return value, 0
        if isinstance(value, AccountMapping):
            return value.account_id, value.topup
        if isinstance(value, dict):
            return value.get("account_id"), int(value.get("topup", 0) or 0)
        return getattr(value, "account_id", None), int(getattr(value, "topup", 0) or 0)

    @classmethod
    def _resolve_route(cls, account_name: str):
        """Resolve a Tap-to-Pay card name to ``(budget, account_id, topup)``.

        The card is looked up in every budget's ``account_mappings``. If it
        is not mapped anywhere, it falls back to the budget flagged
        ``default: true`` and its ``default_account_id``. Returns
        ``(None, None, 0)`` when nothing matches and there is no default.
        """
        budgets = getattr(settings, "budgets", None) or []
        default_budget = None
        for budget in budgets:
            mappings = budget.account_mappings or {}
            if account_name in mappings:
                account_id, topup = cls._unpack_mapping(mappings[account_name])
                return budget.name_or_sync_id, account_id, topup
            if getattr(budget, "default", False):
                default_budget = budget

        if default_budget is not None:
            return default_budget.name_or_sync_id, default_budget.default_account_id, 0

        return None, None, 0

    def add_transactions(self, transactions: List[Transaction]):
        transaction_info_list = []

        # Resolve routing for everything up-front so an unmapped account
        # fails fast, before any budget is opened.
        routed = []  # (tx, budget, account_id, topup)
        for tx in transactions:
            budget, account_id, topup = self._resolve_route(tx.account)
            if not account_id:
                raise ValueError(f"Account name '{tx.account}' is not mapped to an Actual Account ID.")
            routed.append((tx, budget, account_id, topup))

        # Group by target budget, preserving first-seen order.
        groups: "OrderedDict[str, list]" = OrderedDict()
        for item in routed:
            groups.setdefault(item[1], []).append(item)

        for budget, items in groups.items():
            submitted_transactions = []

            with Actual(
                settings.actual_url,
                password=settings.actual_password,
                encryption_password=settings.actual_encryption_password,
                file=budget,
            ) as actual:
                for tx, _budget, account_id, topup in items:
                    # Convert date
                    date = convert_to_date(tx.date)

                    # Apply per-account top-up (no-op when topup == 0)
                    amount, note_suffix = apply_topup(tx.amount, topup)

                    # Determine payee
                    payee = tx.payee or settings.actual_backup_payee

                    # Preserve the original amount in the notes when topped up
                    notes = tx.notes
                    if note_suffix:
                        notes = f"{notes} {note_suffix}".strip() if notes else note_suffix

                    import_id = self._build_import_id(
                        account_id=account_id,
                        amount=amount,
                        date=date,
                        payee=payee,
                        cleared=tx.cleared,
                    )

                    # Prepare transaction info for logging
                    transaction_info = {
                        "Account": tx.account,
                        "Account_ID": account_id,
                        "Budget": budget,
                        "Amount": str(amount),
                        "Original_Amount": str(tx.amount),
                        "Topup": topup,
                        "Date": str(date),
                        "Imported ID": import_id,
                        "Payee": payee,
                        "Notes": notes,
                        "Cleared": tx.cleared,
                    }
                    transaction_info_list.append(transaction_info)

                    # Idempotency: if a transaction with the same imported_id
                    # already exists in this account, skip it. Autoflush makes
                    # this work within the same batch too.
                    existing = self._find_existing_by_imported_id(actual.session, account_id, import_id)
                    if existing is not None:
                        logger.info(f"Skipping duplicate transaction for imported_id={import_id} (existing id={existing.id})")
                        transaction_info["Deduped"] = True
                        continue

                    # Create transaction in Actual
                    try:
                        actual_transaction = create_transaction(
                            s=actual.session,
                            account=account_id,
                            amount=amount,
                            date=date,
                            imported_id=import_id,
                            payee=payee,
                            notes=notes,
                            cleared=tx.cleared,
                            imported_payee=payee,
                        )
                    except Exception as error:
                        if not self._is_duplicate_payee_error(error):
                            raise

                        fallback_payee = self._get_first_matching_payee(actual.session, payee)
                        if fallback_payee is None:
                            raise

                        logger.warning(f"Duplicate payee match detected for '{payee}'. Falling back to first matching payee row.")

                        actual_transaction = create_transaction(
                            s=actual.session,
                            account=account_id,
                            amount=amount,
                            date=date,
                            imported_id=import_id,
                            payee=fallback_payee,
                            notes=notes,
                            cleared=tx.cleared,
                            imported_payee=payee,
                        )
                    submitted_transactions.append(actual_transaction)

                # Run ruleset on submitted transactions
                rs = get_ruleset(actual.session)
                rs.run(submitted_transactions)

                # Commit changes for this budget
                actual.commit()

        # Log transaction info
        logger.info("\n" + json.dumps(transaction_info_list, indent=2))

        return transaction_info_list


# Initialize the service
actual_service = ActualService()
