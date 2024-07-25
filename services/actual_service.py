import json
from decimal import Decimal

from actual import Actual
from actual.queries import create_transaction
from actual.queries import get_ruleset

from core.config import settings
from core.logs import MyLogger
from core.security import generate_custom_id
from core.util import convert_to_date

logger = MyLogger()


class ActualService:
    def __init__(self):
        self.client = None

    def add_transaction(self, account: str, amount: float, date: str, payee: str, notes: str = None, cleared: bool = False):
        with Actual(settings.actual_url, password=settings.actual_password, file=settings.actual_budget) as actual:
            actual_acount_id = settings.account_mappings.get(account, settings.actual_default_account_id)
            date = convert_to_date(date)
            import_id = generate_custom_id()
            transaction_info = {
                "Account": account,
                "Account_ID": actual_acount_id,
                "Amount": str(Decimal(amount)),
                "Date": str(date),
                "Imported ID": import_id,
                "Payee": payee,
                "Notes": notes,
                "Cleared": cleared,
            }
            logger.info("\n" + json.dumps(transaction_info, indent=4))
            # validate account_id
            if not actual_acount_id:
                raise ValueError(f"Account name '{account}' is not mapped to an Actual Account ID.")
            if not payee:
                payee = settings.actual_backup_payee
            t = create_transaction(
                s=actual.session,
                account=actual_acount_id,
                amount=Decimal(amount),
                date=date,
                imported_id=import_id,
                payee=payee,
                notes=notes,
                cleared=cleared,
                imported_payee=payee,
            )
            rs = get_ruleset(actual.session)
            rs.run(t)
            actual.commit()
            return t


# Initialize the service
actual_service = ActualService()
