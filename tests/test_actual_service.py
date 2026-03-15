import unittest
from datetime import date
from unittest.mock import MagicMock
from unittest.mock import patch

from sqlalchemy.orm.exc import MultipleResultsFound

from core.config import settings
from schemas.transactions import Transaction
from services.actual_service import ActualService


class TestActualService(unittest.TestCase):
    def setUp(self):
        self.service = ActualService()

    @patch("services.actual_service.get_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_success(self, mock_actual, mock_create_transaction, mock_get_ruleset):
        # Arrange
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_ruleset = MagicMock()
        mock_get_ruleset.return_value = mock_ruleset

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

    def test_add_transactions_no_account_mapping(self):
        # Arrange
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

    @patch("services.actual_service.get_ruleset")
    @patch("services.actual_service.get_payees")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_duplicate_payee_fallback(
        self, mock_actual, mock_create_transaction, mock_get_payees, mock_get_ruleset
    ):
        # Arrange
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_ruleset = MagicMock()
        mock_get_ruleset.return_value = mock_ruleset

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

    @patch("services.actual_service.get_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    def test_add_transactions_uses_stable_import_id_for_replayed_transaction(
        self, mock_actual, mock_create_transaction, mock_get_ruleset
    ):
        mock_actual_instance = MagicMock()
        mock_actual.return_value.__enter__.return_value = mock_actual_instance
        mock_ruleset = MagicMock()
        mock_get_ruleset.return_value = mock_ruleset

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
