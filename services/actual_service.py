import json
import uuid
from decimal import Decimal
from typing import List

from actual import Actual
from actual.queries import create_transaction
from actual.queries import get_ruleset

from core.config import settings
from core.logs import MyLogger
from core.util import convert_to_date
from schemas.transactions import Transaction

logger = MyLogger()


class ActualService:
    def __init__(self):
        self.client = None

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

                # Convert date and generate import ID
                date = convert_to_date(tx.date)
                import_id = f"ID-{uuid.uuid4()}"

                # Determine payee
                payee = tx.payee or settings.actual_backup_payee

                # Prepare transaction info for logging
                transaction_info = {
                    "Account": tx.account,
                    "Account_ID": account_id,
                    "Amount": str(Decimal(tx.amount)),
                    "Date": str(date),
                    "Imported ID": import_id,
                    "Payee": payee,
                    "Notes": tx.notes,
                    "Cleared": tx.cleared,
                }
                transaction_info_list.append(transaction_info)

                # Create transaction in Actual
                actual_transaction = create_transaction(
                    s=actual.session,
                    account=account_id,
                    amount=Decimal(tx.amount),
                    date=date,
                    imported_id=import_id,
                    payee=payee,
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
