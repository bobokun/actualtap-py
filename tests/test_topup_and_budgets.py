import unittest
from decimal import Decimal
from unittest.mock import MagicMock
from unittest.mock import patch

from core.config import BudgetConfig
from schemas.transactions import Transaction
from services.actual_service import ActualService
from services.actual_service import apply_topup


class TestApplyTopup(unittest.TestCase):
    def test_topup_disabled_is_noop(self):
        amount, note = apply_topup(Decimal("-1.20"), 0)
        self.assertEqual(amount, Decimal("-1.20"))
        self.assertEqual(note, "")

    def test_topup_1x(self):
        cases = {
            "1.00": "2.00",
            "1.20": "2.00",
            "2.30": "3.00",
            "7.50": "8.00",
        }
        for original, expected in cases.items():
            amount, note = apply_topup(Decimal(original), 1)
            self.assertEqual(amount, Decimal(expected), f"1x {original}")
            self.assertIn("topup 1x", note)

    def test_topup_2x(self):
        cases = {
            "1.00": "3.00",
            "1.20": "2.80",
            "2.30": "3.70",
            "7.50": "8.50",
        }
        for original, expected in cases.items():
            amount, _ = apply_topup(Decimal(original), 2)
            self.assertEqual(amount, Decimal(expected), f"2x {original}")

    def test_topup_preserves_negative_sign(self):
        # Spends arrive negative after the API inverts them.
        amount, note = apply_topup(Decimal("-1.20"), 1)
        self.assertEqual(amount, Decimal("-2.00"))
        self.assertIn("orig 1.20 -> 2.00", note)


class TestResolveRoute(unittest.TestCase):
    @patch("services.actual_service.settings")
    def test_string_mapping(self, mock_settings):
        mock_settings.budgets = [
            BudgetConfig(name_or_sync_id="Main", account_mappings={"Card A": "uuid-a"}),
        ]
        self.assertEqual(ActualService._resolve_route("Card A"), ("Main", "uuid-a", 0))

    @patch("services.actual_service.settings")
    def test_object_mapping_with_topup(self, mock_settings):
        mock_settings.budgets = [
            BudgetConfig(
                name_or_sync_id="Main",
                account_mappings={"TR": {"account_id": "uuid-tr", "topup": 2}},
            ),
        ]
        self.assertEqual(ActualService._resolve_route("TR"), ("Main", "uuid-tr", 2))

    @patch("services.actual_service.settings")
    def test_default_budget_fallback(self, mock_settings):
        mock_settings.budgets = [
            BudgetConfig(name_or_sync_id="Other", account_mappings={"Card B": "uuid-b"}),
            BudgetConfig(
                name_or_sync_id="Main",
                default=True,
                default_account_id="default-id",
                account_mappings={"Card A": "uuid-a"},
            ),
        ]
        self.assertEqual(ActualService._resolve_route("Unknown"), ("Main", "default-id", 0))

    @patch("services.actual_service.settings")
    def test_no_match_no_default_returns_none(self, mock_settings):
        mock_settings.budgets = [
            BudgetConfig(name_or_sync_id="Main", account_mappings={"Card A": "uuid-a"}),
        ]
        self.assertEqual(ActualService._resolve_route("Unknown"), (None, None, 0))

    @patch("services.actual_service.settings")
    def test_routes_card_to_its_budget(self, mock_settings):
        mock_settings.budgets = [
            BudgetConfig(
                name_or_sync_id="sync-1",
                default=True,
                default_account_id="def-1",
                account_mappings={"Card A": {"account_id": "uuid-a", "topup": 1}},
            ),
            BudgetConfig(name_or_sync_id="sync-2", account_mappings={"Card B": "uuid-b"}),
        ]
        self.assertEqual(ActualService._resolve_route("Card A"), ("sync-1", "uuid-a", 1))
        self.assertEqual(ActualService._resolve_route("Card B"), ("sync-2", "uuid-b", 0))
        self.assertEqual(ActualService._resolve_route("Card C"), ("sync-1", "def-1", 0))


class TestAddTransactionsMultiBudget(unittest.TestCase):
    @patch("services.actual_service.get_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    @patch("services.actual_service.settings")
    def test_transactions_split_across_budgets(self, mock_settings, mock_actual, mock_create_transaction, mock_get_ruleset):
        mock_settings.actual_url = "http://x"
        mock_settings.actual_password = "p"
        mock_settings.actual_encryption_password = None
        mock_settings.actual_backup_payee = "Unknown"
        mock_settings.budgets = [
            BudgetConfig(name_or_sync_id="sync-1", account_mappings={"Card A": "uuid-a"}),
            BudgetConfig(name_or_sync_id="sync-2", account_mappings={"Card B": "uuid-b"}),
        ]

        mock_actual.return_value.__enter__.return_value = MagicMock()
        mock_get_ruleset.return_value = MagicMock()

        service = ActualService()
        result = service.add_transactions(
            [
                Transaction(account="Card A", date="2023-01-01", amount="10.00", payee="P1"),
                Transaction(account="Card B", date="2023-01-02", amount="20.00", payee="P2"),
            ]
        )

        # One Actual context opened per distinct budget
        opened_files = {call.kwargs["file"] for call in mock_actual.call_args_list}
        self.assertEqual(opened_files, {"sync-1", "sync-2"})
        self.assertEqual(len(result), 2)
        self.assertEqual({r["Budget"] for r in result}, {"sync-1", "sync-2"})

    @patch("services.actual_service.get_ruleset")
    @patch("services.actual_service.create_transaction")
    @patch("services.actual_service.Actual")
    @patch("services.actual_service.settings")
    def test_topup_applied_and_noted(self, mock_settings, mock_actual, mock_create_transaction, mock_get_ruleset):
        mock_settings.actual_url = "http://x"
        mock_settings.actual_password = "p"
        mock_settings.actual_encryption_password = None
        mock_settings.actual_backup_payee = "Unknown"
        mock_settings.budgets = [
            BudgetConfig(
                name_or_sync_id="Main",
                account_mappings={"TR": {"account_id": "uuid-tr", "topup": 1}},
            ),
        ]

        mock_actual.return_value.__enter__.return_value = MagicMock()
        mock_get_ruleset.return_value = MagicMock()

        service = ActualService()
        result = service.add_transactions(
            [Transaction(account="TR", date="2023-01-01", amount="-1.20", payee="Shop", notes="lunch")]
        )

        self.assertEqual(result[0]["Amount"], "-2.00")
        self.assertEqual(result[0]["Original_Amount"], "-1.20")
        self.assertEqual(result[0]["Topup"], 1)
        self.assertIn("topup 1x", result[0]["Notes"])
        self.assertTrue(result[0]["Notes"].startswith("lunch "))
        passed_amount = mock_create_transaction.call_args_list[0].kwargs["amount"]
        self.assertEqual(passed_amount, Decimal("-2.00"))

    @patch("services.actual_service.Actual")
    @patch("services.actual_service.settings")
    def test_unmapped_account_without_default_raises(self, mock_settings, mock_actual):
        mock_settings.actual_url = "http://x"
        mock_settings.actual_password = "p"
        mock_settings.actual_encryption_password = None
        mock_settings.actual_backup_payee = "Unknown"
        mock_settings.budgets = [
            BudgetConfig(name_or_sync_id="Main", account_mappings={"Card A": "uuid-a"}),
        ]
        mock_actual.return_value.__enter__.return_value = MagicMock()

        with self.assertRaises(ValueError):
            ActualService().add_transactions([Transaction(account="Nope", date="2023-01-01", amount="1.00")])


if __name__ == "__main__":
    unittest.main()
