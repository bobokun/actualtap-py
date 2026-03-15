import hashlib
import json
from decimal import Decimal
from typing import List

from actual import Actual
from actual.queries import create_transaction
from actual.queries import get_payees
from actual.queries import get_ruleset
from sqlalchemy.orm.exc import MultipleResultsFound

from core.config import settings
from core.logs import MyLogger
from core.util import convert_to_date
from schemas.transactions import Transaction

logger = MyLogger()


class ActualService:
    def __init__(self):
        self.client = None

    @staticmethod
    def _build_import_id(account_id: str, amount: Decimal, date, payee: str, notes: str, cleared: bool) -> str:
        normalized_amount = format(amount.normalize(), "f")
        normalized_payee = (payee or "").strip().lower()
        normalized_notes = (notes or "").strip().lower()
        cleared_flag = "1" if cleared else "0"
        raw_key = "|".join(
            [
                account_id,
                normalized_amount,
                date.isoformat(),
                normalized_payee,
                normalized_notes,
                cleared_flag,
            ]
        )
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"ID-{digest}"

    @staticmethod
    def _is_duplicate_payee_error(error: Exception) -> bool:
        return isinstance(error, MultipleResultsFound)

    @staticmethod
    def _get_first_matching_payee(session, payee_name: str):
        matching_payees = get_payees(session, name=payee_name)
        if not matching_payees:
            return None
        return matching_payees[0]

    def add_transactions(self, transactions: List[Transaction]):
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
                except ValueError as error:
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

            # Run ruleset on submitted transactions
            rs = get_ruleset(actual.session)
            rs.run(submitted_transactions)

            # Log transaction info
            logger.info("\n" + json.dumps(transaction_info_list, indent=2))

            # Commit changes
            actual.commit()

        return transaction_info_list


# Initialize the service
actual_service = ActualService()
