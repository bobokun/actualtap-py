import hashlib
import json
import time
import typing
import uuid
from decimal import Decimal
from typing import List

from actual import Actual
from actual.database import __TABLE_COLUMNS_MAP__
from actual.database import BaseModel
from actual.queries import create_transaction
from actual.queries import get_payees
from actual.queries import get_rules
from actual.rules import Action
from actual.rules import Condition
from actual.rules import Rule
from actual.rules import RuleSet
from pydantic import TypeAdapter
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlmodel import Column
from sqlmodel import Field
from sqlmodel import Float
from sqlmodel import ForeignKey
from sqlmodel import Integer
from sqlmodel import Text
from sqlmodel import select
from sqlmodel import text

from core.config import settings
from core.logs import MyLogger
from core.util import calculate_distance
from core.util import convert_to_date
from schemas.transactions import Transaction

logger = MyLogger()

DEFAULT_MAX_DISTANCE_METERS = 500.0


class PayeeLocations(BaseModel, table=True):
    """Stores payee geolocation coordinates for Actual Budget."""

    __tablename__ = "payee_locations"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), sa_column=Column("id", Text, primary_key=True))
    payee_id: typing.Optional[str] = Field(default=None, sa_column=Column("payee_id", Text, ForeignKey("payees.id")))
    latitude: typing.Optional[float] = Field(default=None, sa_column=Column("latitude", Float))
    longitude: typing.Optional[float] = Field(default=None, sa_column=Column("longitude", Float))
    created_at: typing.Optional[int] = Field(
        default_factory=lambda: int(time.time() * 1000), sa_column=Column("created_at", Integer)
    )
    tombstone: typing.Optional[int] = Field(default=0, sa_column=Column("tombstone", Integer, server_default=text("0")))


def _register_payee_locations_mapping():
    if "payee_locations" not in __TABLE_COLUMNS_MAP__:
        cols = {c.name: c.name for c in PayeeLocations.__table__.columns}
        __TABLE_COLUMNS_MAP__["payee_locations"] = {
            "entity": PayeeLocations,
            "columns": cols,
            "rev_columns": cols,
        }


_register_payee_locations_mapping()


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

    @classmethod
    def _resolve_payee_id(cls, session, tx: Transaction, actual_tx) -> typing.Optional[str]:
        """Resolve the payee UUID for a created transaction."""
        payee_id = getattr(actual_tx, "payee_id", None)
        if not payee_id and hasattr(actual_tx, "payee") and actual_tx.payee:
            payee_id = getattr(actual_tx.payee, "id", None)
        if not payee_id:
            payee_name = tx.payee or settings.actual_backup_payee
            payee_obj = cls._get_first_matching_payee(session, payee_name)
            if payee_obj:
                payee_id = getattr(payee_obj, "id", None)
        return payee_id

    @classmethod
    def supports_payee_locations(cls, session) -> bool:
        """Return True if the connected budget's database has the payee_locations table (Actual 26.4.0+)."""
        try:
            result = session.exec(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='payee_locations'"))
            return result.first() is not None
        except SQLAlchemyError as e:
            logger.warning(f"Could not verify payee_locations table support: {e}")
            return False

    @classmethod
    def get_payee_locations(cls, session, payee_id: typing.Optional[str] = None) -> list[PayeeLocations]:
        """Retrieve active payee locations, optionally filtered by payee_id (mirrors api/payee-locations-get)."""
        try:
            statement = select(PayeeLocations).where(PayeeLocations.tombstone == 0)
            if payee_id:
                statement = statement.where(PayeeLocations.payee_id == payee_id)
            statement = statement.order_by(PayeeLocations.created_at.desc())
            return list(session.exec(statement).all())
        except SQLAlchemyError as e:
            logger.warning(f"Could not query payee_locations: {e}")
            return []

    @classmethod
    def get_nearby_payees(
        cls, session, latitude: float, longitude: float, max_distance: float = DEFAULT_MAX_DISTANCE_METERS
    ) -> list[dict]:
        """Find active payee locations within max_distance meters (mirrors api/payees-get-nearby).

        Returns a list of dicts with 'payee_id', 'location', and 'distance' sorted by distance.
        """
        locations = cls.get_payee_locations(session)
        nearby = []
        for loc in locations:
            if loc.latitude is not None and loc.longitude is not None and loc.payee_id:
                dist = calculate_distance(latitude, longitude, float(loc.latitude), float(loc.longitude))
                if dist <= max_distance:
                    nearby.append(
                        {
                            "payee_id": loc.payee_id,
                            "location": loc,
                            "distance": dist,
                        }
                    )
        nearby.sort(key=lambda x: x["distance"])
        return nearby

    @classmethod
    def create_payee_location(
        cls, session, payee_id: str, latitude: float, longitude: float, max_distance: float = DEFAULT_MAX_DISTANCE_METERS
    ) -> typing.Optional[PayeeLocations]:
        """Create a payee location if one does not already exist within max_distance (mirrors api/payee-location-create)."""
        try:
            locations = cls.get_payee_locations(session, payee_id=payee_id)
            if any(
                location.latitude is not None
                and location.longitude is not None
                and calculate_distance(latitude, longitude, float(location.latitude), float(location.longitude)) <= max_distance
                for location in locations
            ):
                logger.info(f"Payee location for payee ID '{payee_id}' already exists within " f"{max_distance}m. Skipping.")
                return None

            payee_loc = PayeeLocations(
                id=str(uuid.uuid4()),
                payee_id=payee_id,
                latitude=latitude,
                longitude=longitude,
                created_at=int(time.time() * 1000),
                tombstone=0,
            )
            session.add(payee_loc)
            logger.info(f"Saved new payee location for payee ID '{payee_id}'")
            return payee_loc
        except SQLAlchemyError as e:
            logger.warning(f"Failed to create payee location for payee ID '{payee_id}': {e}")
            return None

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
                    "Type": tx.type,
                }
                if tx.latitude is not None and tx.longitude is not None:
                    transaction_info["Latitude"] = tx.latitude
                    transaction_info["Longitude"] = tx.longitude
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

            # Save payee locations if coordinates are provided (requires Actual 26.4.0+ for the payee_locations table)
            has_locations = any(tx.latitude is not None and tx.longitude is not None for tx in transactions)
            if has_locations and not self.supports_payee_locations(actual.session):
                logger.warning(
                    "Skipping payee location save(s): connected Actual server does not have the "
                    "'payee_locations' table (requires Actual 26.4.0+)."
                )
                has_locations = False
            if has_locations:
                for tx, actual_tx in zip(transactions, submitted_transactions):
                    if tx.latitude is not None and tx.longitude is not None:
                        payee_id = self._resolve_payee_id(actual.session, tx, actual_tx)
                        if payee_id:
                            self.create_payee_location(
                                session=actual.session,
                                payee_id=payee_id,
                                latitude=float(tx.latitude),
                                longitude=float(tx.longitude),
                            )

            # Log transaction info
            logger.info("\n" + json.dumps(transaction_info_list, indent=2))

            # Commit changes
            actual.commit()

        return transaction_info_list


# Initialize the service
actual_service = ActualService()
