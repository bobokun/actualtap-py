import hashlib
import json
import typing
from decimal import Decimal
from typing import List

from actual import Actual
from actual.queries import create_transaction
from actual.queries import get_payees
from actual.queries import get_rules
from actual.rules import Action
from actual.rules import Condition
from actual.rules import Rule
from actual.rules import RuleSet
from pydantic import TypeAdapter
from sqlalchemy.orm.exc import MultipleResultsFound

from core.config import settings
from core.logs import MyLogger
from core.util import convert_to_date
from schemas.transactions import Transaction

logger = MyLogger()


class ActualService:
    """Service layer for interacting with the Actual Budget API."""

    def __init__(self):
        self.client = None

    @staticmethod
    def _build_import_id(account_id: str, amount: Decimal, date, payee: str, notes: str, cleared: bool) -> str:
        """Build a deterministic SHA-256-based import ID for a transaction.

        The ID is derived from the account ID, amount, date, payee, notes, and
        cleared flag so that identical transactions always produce the same ID,
        allowing Actual Budget to detect and skip duplicates on re-import.
        """
        normalized_amount = format(amount.normalize(), "f")
        normalized_payee = (payee or "").strip().lower()
        normalized_notes = (notes or "").strip().lower()
        cleared_flag = "1" if cleared else "0"
        raw_key = json.dumps(
            [
                account_id,
                normalized_amount,
                date.isoformat(),
                normalized_payee,
                normalized_notes,
                cleared_flag,
            ],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"ID-{digest}"

    @staticmethod
    def _is_duplicate_payee_error(error: Exception) -> bool:
        """Return True if the exception indicates a duplicate payee lookup result."""
        return isinstance(error, MultipleResultsFound) or "Multiple rows were found when one or none was required" in str(error)

    @staticmethod
    def _get_first_matching_payee(session, payee_name: str):
        """Return the first payee matching the given name, or None if not found."""
        matching_payees = get_payees(session, name=payee_name)
        if not matching_payees:
            return None
        return matching_payees[0]

    @staticmethod
    def _build_ruleset(session) -> RuleSet:
        """Build a RuleSet from the database, skipping any rules that fail validation.

        Valid action fields are derived dynamically from the ``Action`` model's
        type annotation so the check stays in sync with the installed version of
        ``actualpy``.  Any rule whose actions reference an unrecognised field is
        logged as a warning and excluded from the returned RuleSet rather than
        aborting the entire import.
        """
        _field_annotation = Action.model_fields["field"].annotation
        valid_action_fields = {
            v
            for arg in typing.get_args(_field_annotation)
            for v in (typing.get_args(arg) if typing.get_origin(arg) is typing.Literal else ())
        }
        condition_adapter = TypeAdapter(list[Condition])
        action_adapter = TypeAdapter(list[Action])
        valid_rules = []
        for raw_rule in get_rules(session):
            if not raw_rule.conditions or not raw_rule.actions:
                continue
            try:
                conditions = condition_adapter.validate_json(raw_rule.conditions)
                actions = action_adapter.validate_json(raw_rule.actions)
                valid_rules.append(
                    Rule(
                        conditions=conditions,
                        operation=raw_rule.conditions_op,
                        actions=actions,
                        stage=raw_rule.stage,
                    )
                )
            except Exception as rule_error:
                try:
                    raw_actions = json.loads(raw_rule.actions)
                    bad_fields = [
                        a.get("field")
                        for a in raw_actions
                        if isinstance(a, dict) and a.get("field") not in valid_action_fields and a.get("field") is not None
                    ]
                    raw_conditions = json.loads(raw_rule.conditions or "[]")
                    condition_summary = ", ".join(
                        f"{c.get('field')} {c.get('op')} '{c.get('value')}'" for c in raw_conditions if isinstance(c, dict)
                    )
                except json.JSONDecodeError:
                    bad_fields = []
                    condition_summary = "(unreadable)"
                logger.warning(
                    f"Skipping rule ID '{raw_rule.id}' (stage={raw_rule.stage!r}, "
                    f"conditions: [{condition_summary}])"
                    + (f" — unsupported action field(s): {bad_fields}" if bad_fields else f": {rule_error}")
                )
        return RuleSet(rules=valid_rules)

    def add_transactions(self, transactions: List[Transaction]):
        """Add a list of transactions to Actual Budget.

        For each transaction, the account name is resolved to an Actual account
        ID using the configured mappings.  A deterministic import ID is generated
        so duplicate submissions are ignored by Actual Budget.  After all
        transactions are created, the full ruleset is applied (with invalid rules
        skipped), and the session is committed.

        Returns a list of dicts containing the logged details for each transaction.
        """
        transaction_info_list = []
        submitted_transactions = []

        with Actual(
            settings.actual_url,
            password=settings.actual_password,
            encryption_password=settings.actual_encryption_password,
            file=settings.actual_budget,
        ) as actual:
            for tx in transactions:
                # Map account name to Actual account ID
                account_id = settings.account_mappings.get(tx.account, settings.actual_default_account_id)
                if not account_id:
                    raise ValueError(f"Account name '{tx.account}' is not mapped to an Actual Account ID.")

                # Convert date and generate deterministic import ID
                date = convert_to_date(tx.date)
                amount = tx.amount

                # Determine payee
                payee = tx.payee or settings.actual_backup_payee
                import_id = self._build_import_id(
                    account_id=account_id,
                    amount=amount,
                    date=date,
                    payee=payee,
                    notes=tx.notes,
                    cleared=tx.cleared,
                )

                # Prepare transaction info for logging
                transaction_info = {
                    "Account": tx.account,
                    "Account_ID": account_id,
                    "Amount": str(amount),
                    "Date": str(date),
                    "Imported ID": import_id,
                    "Payee": payee,
                    "Notes": tx.notes,
                    "Cleared": tx.cleared,
                }
                transaction_info_list.append(transaction_info)

                # Create transaction in Actual
                try:
                    actual_transaction = create_transaction(
                        s=actual.session,
                        account=account_id,
                        amount=amount,
                        date=date,
                        imported_id=import_id,
                        payee=payee,
                        notes=tx.notes,
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
                        notes=tx.notes,
                        cleared=tx.cleared,
                        imported_payee=payee,
                    )
                submitted_transactions.append(actual_transaction)

            # Run ruleset on submitted transactions, skipping any rules that fail validation
            self._build_ruleset(actual.session).run(submitted_transactions)

            # Log transaction info
            logger.info("\n" + json.dumps(transaction_info_list, indent=2))

            # Commit changes
            actual.commit()

        return transaction_info_list


# Initialize the service
actual_service = ActualService()
