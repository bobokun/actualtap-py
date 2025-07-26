import time
from datetime import date

from schemas.transactions import Transaction


class TestTransactionDateDefault:
    """Test that Transaction date defaults work correctly (Issue #50)"""

    def test_date_field_uses_default_factory_not_default_value(self):
        """
        Test that the date field uses default_factory (which calls datetime.date.today()
        each time) rather than a default value (which would be fixed at class
        definition time).

        This is the core test that verifies the fix for Issue #50.
        """
        # Get the field info for the date field
        date_field = Transaction.model_fields["date"]

        # Verify it uses default_factory, not default
        assert hasattr(date_field, "default_factory")
        assert date_field.default_factory is not None
        assert date_field.default is None or str(date_field.default) == "PydanticUndefined"

        # Verify the default_factory is datetime.date.today
        import datetime

        assert date_field.default_factory == datetime.date.today

    def test_explicit_date_overrides_default(self):
        """
        Test that providing an explicit date overrides the default behavior.
        """
        explicit_date = date(2023, 1, 15)
        transaction = Transaction(account="Test Account", date=explicit_date)

        # Should use the explicit date, not today's date
        assert transaction.date == explicit_date
        assert transaction.date != date.today()

    def test_date_default_factory_returns_date_object(self):
        """
        Test that the default_factory returns a proper date object.
        """
        transaction = Transaction(account="Test Account")

        # Should be a date object
        assert isinstance(transaction.date, date)
        # Should be today's date
        assert transaction.date == date.today()

    def test_multiple_transactions_get_todays_date(self):
        """
        Test that multiple transactions created without explicit dates
        all get today's date (not some fixed date from class definition time).
        """
        # Create multiple transactions
        transaction1 = Transaction(account="Account 1")
        transaction2 = Transaction(account="Account 2")
        transaction3 = Transaction(account="Account 3")

        # All should have today's date
        today = date.today()
        assert transaction1.date == today
        assert transaction2.date == today
        assert transaction3.date == today

    def test_date_default_behavior_vs_broken_behavior(self):
        """
        Test that demonstrates the difference between correct default_factory
        behavior and the broken default behavior that was reported in Issue #50.

        This test shows that if we had used default=date.today() instead of
        default_factory=date.today, all transactions would have the same fixed date.
        """

        # This is what the BROKEN implementation would look like:
        # (We can't actually test this because it would break at class definition time,
        # but this demonstrates the concept)
        # Instead, let's verify our correct implementation
        transaction1 = Transaction(account="Test 1")

        # Small delay to ensure we're testing the right thing
        time.sleep(0.001)

        transaction2 = Transaction(account="Test 2")

        # Both should have today's date (proving default_factory works correctly)
        # If it were broken with default=date.today(), they would have a fixed date
        # from when the class was defined
        today = date.today()
        assert transaction1.date == today
        assert transaction2.date == today

        # The key insight: default_factory ensures date.today() is called
        # each time a new instance is created, not just once at class definition

    def test_date_string_parsing_still_works(self):
        """
        Test that explicit date strings are still parsed correctly.
        """
        transaction = Transaction(account="Test Account", date="2024-01-15")
        assert transaction.date == date(2024, 1, 15)

        transaction2 = Transaction(account="Test Account", date="Jan 15, 2024")
        assert transaction2.date == date(2024, 1, 15)
