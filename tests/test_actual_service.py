import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

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
                account="Test Account", date="2023-01-01", amount="10.00", payee="Test Payee", notes="Test Note", cleared=True
            ),
            Transaction(account="Another Account", date="2023-01-02", amount="-20.50", payee="", notes="", cleared=False),
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
                account="Unmapped Account", date="2023-01-01", amount="10.00", payee="Test Payee", notes="Test Note", cleared=True
            )
        ]
        settings.account_mappings = {}
        settings.actual_default_account_id = None

        # Act & Assert
        with self.assertRaises(ValueError):
            self.service.add_transactions(transactions)
