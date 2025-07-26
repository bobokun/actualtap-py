from datetime import date
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas.transactions import Transaction


class TestTransactionSchema:
    """Test Transaction schema validation"""

    def test_transaction_valid_minimal(self):
        """Test transaction with minimal required fields"""
        transaction = Transaction(account="Test Account")
        assert transaction.account == "Test Account"
        assert transaction.amount == Decimal("0")
        assert isinstance(transaction.date, datetime)
        assert transaction.payee is None
        assert transaction.notes is None
        assert transaction.cleared is False

    def test_transaction_valid_complete(self):
        """Test transaction with all fields"""
        transaction = Transaction(
            account="Test Account", amount=100.50, date="2024-01-01", payee="Test Payee", notes="Test notes", cleared=True
        )
        assert transaction.account == "Test Account"
        assert transaction.amount == Decimal("100.50")
        assert isinstance(transaction.date, datetime)
        assert transaction.payee == "Test Payee"
        assert transaction.notes == "Test notes"
        assert transaction.cleared is True

    def test_amount_validation_string_number(self):
        """Test amount validation with string number"""
        transaction = Transaction(account="Test", amount="123.45")
        assert transaction.amount == Decimal("123.45")

    def test_amount_validation_comma_decimal(self):
        """Test amount validation with comma as decimal separator"""
        transaction = Transaction(account="Test", amount="123,45")
        assert transaction.amount == Decimal("123.45")

    def test_amount_validation_zero(self):
        """Test amount validation with zero"""
        transaction = Transaction(account="Test", amount=0)
        assert transaction.amount == Decimal("0")

    def test_amount_validation_negative(self):
        """Test amount validation with negative number"""
        transaction = Transaction(account="Test", amount=-50.25)
        assert transaction.amount == Decimal("-50.25")

    def test_amount_validation_invalid_string(self):
        """Test amount validation with invalid string"""
        with pytest.raises(ValidationError) as exc_info:
            Transaction(account="Test", amount="not-a-number")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "Invalid amount format" in str(errors[0]["ctx"]["error"])

    def test_amount_validation_empty_string(self):
        """Test amount validation with empty string"""
        transaction = Transaction(account="Test", amount="")
        assert transaction.amount == Decimal("0")

    def test_amount_validation_none(self):
        """Test amount validation with None"""
        transaction = Transaction(account="Test", amount=None)
        assert transaction.amount == Decimal("0")

    def test_date_validation_iso_format(self):
        """Test date validation with ISO format"""
        transaction = Transaction(account="Test", date="2024-01-01")
        assert isinstance(transaction.date, datetime)
        assert transaction.date.year == 2024
        assert transaction.date.month == 1
        assert transaction.date.day == 1

    def test_date_validation_datetime_object(self):
        """Test date validation with datetime object"""
        test_date = datetime(2024, 1, 1, 12, 30, 45)
        transaction = Transaction(account="Test", date=test_date)
        # The schema converts datetime to date and back to datetime at midnight
        expected_date = datetime(2024, 1, 1, 0, 0)
        assert transaction.date == expected_date

    def test_date_validation_date_object(self):
        """Test date validation with date object"""
        test_date = date(2024, 1, 1)
        transaction = Transaction(account="Test", date=test_date)
        assert isinstance(transaction.date, datetime)
        assert transaction.date.year == 2024
        assert transaction.date.month == 1
        assert transaction.date.day == 1
        assert transaction.date.hour == 0
        assert transaction.date.minute == 0

    def test_date_validation_invalid_format(self):
        """Test date validation with invalid format"""
        with pytest.raises(ValidationError) as exc_info:
            Transaction(account="Test", date="invalid-date")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "date" in errors[0]["loc"]

    def test_account_required(self):
        """Test that account field is required"""
        with pytest.raises(ValidationError) as exc_info:
            Transaction()

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("account",)
        assert errors[0]["type"] == "missing"

    def test_optional_fields_none(self):
        """Test that optional fields can be None"""
        transaction = Transaction(account="Test", payee=None, notes=None)
        assert transaction.payee is None
        assert transaction.notes is None

    def test_cleared_boolean_conversion(self):
        """Test cleared field boolean conversion"""
        # Test with string "true"
        transaction1 = Transaction(account="Test", cleared="true")
        assert transaction1.cleared is True

        # Test with string "false"
        transaction2 = Transaction(account="Test", cleared="false")
        assert transaction2.cleared is False

        # Test with integer 1
        transaction3 = Transaction(account="Test", cleared=1)
        assert transaction3.cleared is True

        # Test with integer 0
        transaction4 = Transaction(account="Test", cleared=0)
        assert transaction4.cleared is False

    def test_date_validation_datetime_return_path(self):
        """Test date validation when convert_to_date returns a datetime object"""
        from datetime import datetime
        from unittest.mock import patch

        # Mock convert_to_date to return a datetime object (not a date)
        test_datetime = datetime(2024, 1, 1, 12, 30, 45)
        with patch("schemas.transactions.convert_to_date", return_value=test_datetime):
            transaction = Transaction(account="Test", date="2024-01-01")
            # This should hit line 41 where it returns the datetime directly
            assert transaction.date == test_datetime
