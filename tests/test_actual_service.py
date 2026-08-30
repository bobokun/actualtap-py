import unittest
from datetime import date
from unittest.mock import MagicMock
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import MultipleResultsFound

from core.config import settings
from schemas.transactions import Transaction
from services.actual_service import ActualService
from services.actual_service import PayeeLocations


class TestActualService(unittest.TestCase):
    def setUp(self):
        self.service = ActualService()

    @patch.object(ActualService, "_build_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_success(self, mock_actual, mock_create_transaction, mock_build_ruleset):
        # Arrange
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_ruleset = MagicMock()
        mock_build_ruleset.return_value = mock_ruleset

        transactions = [
            Transaction(
                account="Test Account",
                date="2023-01-01",
                amount="10.00",
                payee="Test Payee",
                notes="Test Note",
                cleared=True,
            ),
            Transaction(
                account="Another Account",
                date="2023-01-02",
                amount="-20.50",
                payee="",
                notes="",
                cleared=False,
            ),
        ]

        settings.account_mappings = {"Test Account": "actual-account-id"}
        settings.actual_default_account_id = "default-account-id"
        settings.actual_backup_payee = "Backup Payee"

        # Act
        result = self.service.add_transactions(transactions)

        # Assert
        self.assertEqual(len(result), 2)
        mock_actual_instance.commit.assert_called_once()
        self.assertEqual(mock_create_transaction.call_count, 2)
        mock_ruleset.run.assert_called_once()

        # Check first transaction
        self.assertEqual(result[0]["Account"], "Test Account")
        self.assertEqual(result[0]["Account_ID"], "actual-account-id")
        self.assertEqual(result[0]["Amount"], "10.00")
        self.assertEqual(result[0]["Payee"], "Test Payee")

        # Check second transaction (uses default account and backup payee)
        self.assertEqual(result[1]["Account"], "Another Account")
        self.assertEqual(result[1]["Account_ID"], "default-account-id")
        self.assertEqual(result[1]["Amount"], "-20.50")
        self.assertEqual(result[1]["Payee"], "Backup Payee")

    @patch("services.actual_service.Actual")
    def test_add_transactions_no_account_mapping(self, mock_actual):
        # Arrange
        mock_actual.return_value.__enter__.return_value = MagicMock()
        transactions = [
            Transaction(
                account="Unmapped Account",
                date="2023-01-01",
                amount="10.00",
                payee="Test Payee",
                notes="Test Note",
                cleared=True,
            )
        ]
        settings.account_mappings = {}
        settings.actual_default_account_id = None

        # Act & Assert
        with self.assertRaises(ValueError):
            self.service.add_transactions(transactions)

    def test_build_import_id_is_deterministic_and_normalized(self):
        import_id_one = self.service._build_import_id(
            account_id="actual-account-id",
            amount=Transaction(account="A", amount="10.00").amount,
            date=date(2023, 1, 1),
            payee=" McDONALDS #2322 ",
            notes=" Lunch ",
            cleared=False,
        )

        import_id_two = self.service._build_import_id(
            account_id="actual-account-id",
            amount=Transaction(account="A", amount="10").amount,
            date=date(2023, 1, 1),
            payee="mcdonalds #2322",
            notes="lunch",
            cleared=False,
        )

        self.assertEqual(import_id_one, import_id_two)
        self.assertTrue(import_id_one.startswith("ID-"))

    @patch.object(ActualService, "_build_ruleset")
    @patch("services.actual_service.get_payees")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_duplicate_payee_fallback(
        self, mock_actual, mock_create_transaction, mock_get_payees, mock_build_ruleset
    ):
        # Arrange
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_ruleset = MagicMock()
        mock_build_ruleset.return_value = mock_ruleset

        duplicate_payee_error = MultipleResultsFound("Multiple rows were found when one or none was required")
        successful_transaction = MagicMock()
        mock_create_transaction.side_effect = [
            duplicate_payee_error,
            successful_transaction,
        ]
        fallback_payee = MagicMock()
        mock_get_payees.return_value = [fallback_payee]

        transactions = [
            Transaction(
                account="Test Account",
                date="2023-01-01",
                amount="10.00",
                payee="Duplicate Payee",
                notes="Test Note",
                cleared=True,
            )
        ]

        settings.account_mappings = {"Test Account": "actual-account-id"}
        settings.actual_default_account_id = "default-account-id"
        settings.actual_backup_payee = "Backup Payee"

        # Act
        result = self.service.add_transactions(transactions)

        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(mock_create_transaction.call_count, 2)

        first_call = mock_create_transaction.call_args_list[0].kwargs
        second_call = mock_create_transaction.call_args_list[1].kwargs

        self.assertEqual(first_call["payee"], "Duplicate Payee")
        self.assertEqual(first_call["imported_payee"], "Duplicate Payee")

        self.assertEqual(second_call["payee"], fallback_payee)
        self.assertEqual(second_call["imported_payee"], "Duplicate Payee")
        mock_get_payees.assert_called_once_with(mock_actual_instance.session, name="Duplicate Payee")

        mock_ruleset.run.assert_called_once_with([successful_transaction])
        mock_actual_instance.commit.assert_called_once()

    @patch.object(ActualService, "_build_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_uses_stable_import_id_for_replayed_transaction(
        self, mock_actual, mock_create_transaction, mock_build_ruleset
    ):
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_ruleset = MagicMock()
        mock_build_ruleset.return_value = mock_ruleset

        settings.account_mappings = {"Test Account": "actual-account-id"}
        settings.actual_default_account_id = "default-account-id"
        settings.actual_backup_payee = "Backup Payee"

        tx = Transaction(
            account="Test Account",
            date="2023-01-01",
            amount="10.00",
            payee="McDonalds #2322",
            notes="Test Note",
            cleared=True,
        )

        self.service.add_transactions([tx])
        self.service.add_transactions([tx])

        self.assertEqual(mock_create_transaction.call_count, 2)
        first_import_id = mock_create_transaction.call_args_list[0].kwargs["imported_id"]
        second_import_id = mock_create_transaction.call_args_list[1].kwargs["imported_id"]
        self.assertEqual(first_import_id, second_import_id)

    @patch.object(ActualService, "_build_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_with_location_saves_payee_location(self, mock_actual, mock_create_transaction, mock_build_ruleset):
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_ruleset = MagicMock()
        mock_build_ruleset.return_value = mock_ruleset

        mock_tx = MagicMock()
        mock_tx.payee_id = "payee-123"
        mock_create_transaction.return_value = mock_tx

        # Mock session.exec for get_payee_locations returning empty list
        mock_exec_result = MagicMock()
        mock_exec_result.all.return_value = []
        mock_actual_instance.session.exec.return_value = mock_exec_result

        settings.account_mappings = {"Test Account": "actual-account-id"}
        settings.actual_default_account_id = "default-account-id"
        settings.actual_backup_payee = "Backup Payee"

        tx = Transaction(
            account="Test Account",
            date="2023-01-01",
            amount="10.00",
            payee="Coffee Shop",
            latitude=37.7749,
            longitude=-122.4194,
        )

        result = self.service.add_transactions([tx])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Latitude"], 37.7749)
        self.assertEqual(result[0]["Longitude"], -122.4194)

        # Verify payee location was added to the session
        added_objects = [call[0][0] for call in mock_actual_instance.session.add.call_args_list]
        payee_loc_objects = [obj for obj in added_objects if isinstance(obj, PayeeLocations)]
        self.assertEqual(len(payee_loc_objects), 1)
        self.assertEqual(payee_loc_objects[0].payee_id, "payee-123")
        self.assertEqual(payee_loc_objects[0].latitude, 37.7749)
        self.assertEqual(payee_loc_objects[0].longitude, -122.4194)

    @patch.object(ActualService, "_build_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_with_nearby_location_skips_duplicate(
        self, mock_actual, mock_create_transaction, mock_build_ruleset
    ):
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_ruleset = MagicMock()
        mock_build_ruleset.return_value = mock_ruleset

        mock_tx = MagicMock()
        mock_tx.payee_id = "payee-123"
        mock_create_transaction.return_value = mock_tx

        # Mock existing location within 500m
        existing_loc = PayeeLocations(payee_id="payee-123", latitude=37.7749, longitude=-122.4194)
        mock_exec_result = MagicMock()
        mock_exec_result.all.return_value = [existing_loc]
        mock_actual_instance.session.exec.return_value = mock_exec_result

        settings.account_mappings = {"Test Account": "actual-account-id"}
        settings.actual_default_account_id = "default-account-id"
        settings.actual_backup_payee = "Backup Payee"

        tx = Transaction(
            account="Test Account",
            date="2023-01-01",
            amount="10.00",
            payee="Coffee Shop",
            latitude=37.77491,
            longitude=-122.41941,
        )

        result = self.service.add_transactions([tx])

        self.assertEqual(len(result), 1)
        # Should not add another PayeeLocations object
        added_objects = [call[0][0] for call in mock_actual_instance.session.add.call_args_list]
        payee_loc_objects = [obj for obj in added_objects if isinstance(obj, PayeeLocations)]
        self.assertEqual(len(payee_loc_objects), 0)

    @patch.object(ActualService, "_build_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_with_location_uses_payee_after_rules(
        self, mock_actual, mock_create_transaction, mock_build_ruleset
    ):
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_tx = MagicMock()
        mock_tx.payee_id = "initial-payee"
        mock_create_transaction.return_value = mock_tx
        mock_ruleset = MagicMock()
        mock_ruleset.run.side_effect = lambda transactions: setattr(transactions[0], "payee_id", "rule-payee")
        mock_build_ruleset.return_value = mock_ruleset
        mock_exec_result = MagicMock()
        mock_exec_result.all.return_value = []
        mock_actual_instance.session.exec.return_value = mock_exec_result

        settings.account_mappings = {"Test Account": "actual-account-id"}
        settings.actual_default_account_id = "default-account-id"
        settings.actual_backup_payee = "Backup Payee"

        self.service.add_transactions(
            [
                Transaction(
                    account="Test Account",
                    date="2023-01-01",
                    amount="10.00",
                    payee="Coffee Shop",
                    latitude=37.7749,
                    longitude=-122.4194,
                )
            ]
        )

        added_objects = [call[0][0] for call in mock_actual_instance.session.add.call_args_list]
        payee_loc_objects = [obj for obj in added_objects if isinstance(obj, PayeeLocations)]
        self.assertEqual(len(payee_loc_objects), 1)
        self.assertEqual(payee_loc_objects[0].payee_id, "rule-payee")

    def test_get_nearby_payees_and_locations(self):
        mock_session = MagicMock()
        loc1 = PayeeLocations(id="loc-1", payee_id="payee-1", latitude=40.7128, longitude=-74.0060)
        loc2 = PayeeLocations(id="loc-2", payee_id="payee-2", latitude=40.7589, longitude=-73.9851)
        mock_exec_result = MagicMock()
        mock_exec_result.all.return_value = [loc1, loc2]
        mock_session.exec.return_value = mock_exec_result

        # Query nearby for point close to loc1 (within 200m)
        nearby = ActualService.get_nearby_payees(mock_session, 40.7130, -74.0060, max_distance=500.0)
        self.assertEqual(len(nearby), 1)
        self.assertEqual(nearby[0]["payee_id"], "payee-1")
        self.assertEqual(nearby[0]["location"].id, "loc-1")

    def test_payee_locations_model_convert(self):
        loc = PayeeLocations(payee_id="payee-abc", latitude=40.7128, longitude=-74.0060)
        messages = loc.convert(is_new=True)
        col_map = {m.column: m.value for m in messages}
        self.assertEqual(col_map.get("payee_id"), "S:payee-abc")
        self.assertEqual(col_map.get("latitude"), "N:40.7128")
        self.assertEqual(col_map.get("longitude"), "N:-74.006")
        self.assertEqual(col_map.get("tombstone"), "N:0")

    def test_supports_payee_locations_true(self):
        mock_session = MagicMock()
        mock_exec_result = MagicMock()
        mock_exec_result.first.return_value = (1,)
        mock_session.exec.return_value = mock_exec_result

        self.assertTrue(ActualService.supports_payee_locations(mock_session))

    def test_supports_payee_locations_false_when_table_missing(self):
        mock_session = MagicMock()
        mock_exec_result = MagicMock()
        mock_exec_result.first.return_value = None
        mock_session.exec.return_value = mock_exec_result

        self.assertFalse(ActualService.supports_payee_locations(mock_session))

    def test_supports_payee_locations_false_on_db_error(self):
        mock_session = MagicMock()
        mock_session.exec.side_effect = SQLAlchemyError("boom")

        self.assertFalse(ActualService.supports_payee_locations(mock_session))

    @patch.object(ActualService, "_build_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_skips_location_when_table_unsupported(
        self, mock_actual, mock_create_transaction, mock_build_ruleset
    ):
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_build_ruleset.return_value = MagicMock()

        mock_tx = MagicMock()
        mock_tx.payee_id = "payee-123"
        mock_create_transaction.return_value = mock_tx

        # sqlite_master lookup for payee_locations support returns nothing
        mock_exec_result = MagicMock()
        mock_exec_result.first.return_value = None
        mock_actual_instance.session.exec.return_value = mock_exec_result

        settings.account_mappings = {"Test Account": "actual-account-id"}
        settings.actual_default_account_id = "default-account-id"
        settings.actual_backup_payee = "Backup Payee"

        tx = Transaction(
            account="Test Account",
            date="2023-01-01",
            amount="10.00",
            payee="Coffee Shop",
            latitude=37.7749,
            longitude=-122.4194,
        )

        result = self.service.add_transactions([tx])

        self.assertEqual(len(result), 1)
        added_objects = [call[0][0] for call in mock_actual_instance.session.add.call_args_list]
        payee_loc_objects = [obj for obj in added_objects if isinstance(obj, PayeeLocations)]
        self.assertEqual(len(payee_loc_objects), 0)
