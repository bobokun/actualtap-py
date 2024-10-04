import json
from decimal import Decimal
from typing import List

from actual import Actual
from actual.queries import create_transaction
from actual.queries import get_ruleset

from core.config import settings
from core.logs import MyLogger
from core.security import generate_custom_id
from core.util import convert_to_date
from models.transaction import Transaction

logger = MyLogger()


class ActualService:
    def __init__(self):
        self.client = None

    def add_transactions(self, transactions: List[Transaction]):
        transaction_info_list = []
        submitted_transactions = []
        with Actual(settings.actual_url, password=settings.actual_password, file=settings.actual_budget) as actual:
            for t in transactions:
                actual_acount_id = settings.account_mappings.get(t.account, settings.actual_default_account_id)
                date = convert_to_date(t.date)
                import_id = generate_custom_id()
                transaction_info = {
                    "Account": t.account,
                    "Account_ID": actual_acount_id,
                    "Amount": str(Decimal(t.amount)),
                    "Date": str(date),
                    "Imported ID": import_id,
                    "Payee": t.payee,
                    "Notes": t.notes,
                    "Cleared": t.cleared,
                }
                transaction_info_list.append(transaction_info)
                # validate account_id
                if not actual_acount_id:
                    raise ValueError(f"Account name '{t.account}' is not mapped to an Actual Account ID.")
                if not t.payee:
                    payee = settings.actual_backup_payee
                else:
                    payee = t.payee
                t = create_transaction(
                    s=actual.session,
                    account=actual_acount_id,
                    amount=Decimal(t.amount),
                    date=date,
                    imported_id=import_id,
                    payee=t.payee,
                    notes=t.notes,
                    cleared=t.cleared,
                    imported_payee=payee,
                )
                submitted_transactions.append(t)
            rs = get_ruleset(actual.session)
            rs.run(submitted_transactions)
            logger.info("\n" + json.dumps(transaction_info_list, indent=2))
            actual.commit()
            return transaction_info_list


# Initialize the service
actual_service = ActualService()
