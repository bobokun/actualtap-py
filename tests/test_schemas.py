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
        assert isinstance(transaction.date, date)
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
        assert isinstance(transaction.date, date)
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
        assert isinstance(transaction.date, date)
        assert transaction.date.year == 2024
        assert transaction.date.month == 1
        assert transaction.date.day == 1

    def test_date_validation_datetime_object(self):
        """Test date validation with datetime object"""
        test_date = datetime(2024, 1, 1, 12, 30, 45)
        transaction = Transaction(account="Test", date=test_date)
        # The schema converts datetime to date
        expected_date = date(2024, 1, 1)
        assert transaction.date == expected_date

    def test_date_validation_date_object(self):
        """Test date validation with date object"""
        test_date = date(2024, 1, 1)
        transaction = Transaction(account="Test", date=test_date)
        assert isinstance(transaction.date, date)
        assert transaction.date.year == 2024
        assert transaction.date.month == 1
        assert transaction.date.day == 1

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
            # Since the field is typed as date, Pydantic converts datetime to date
            expected_date = date(2024, 1, 1)
            assert transaction.date == expected_date

    def test_location_validation_valid_numbers(self):
        """Test location validation with numeric latitude and longitude"""
        transaction = Transaction(account="Test", latitude=37.7749, longitude=-122.4194)
        assert transaction.latitude == 37.7749
        assert transaction.longitude == -122.4194
        assert transaction.location is not None
        assert transaction.location.latitude == 37.7749
        assert transaction.location.longitude == -122.4194

    def test_location_validation_string_coordinates(self):
        """Test location validation with string coordinates and comma decimals"""
        transaction = Transaction(account="Test", latitude="37,7749", longitude="-122.4194")
        assert transaction.latitude == 37.7749
        assert transaction.longitude == -122.4194

    def test_location_validation_aliases(self):
        """Test location validation with alias fields lat, long, lng, lon"""
        tx1 = Transaction(account="Test", lat=40.7128, long=-74.0060)
        assert tx1.latitude == 40.7128
        assert tx1.longitude == -74.0060

        tx2 = Transaction(account="Test", lat=40.7128, lng=-74.0060)
        assert tx2.latitude == 40.7128
        assert tx2.longitude == -74.0060

        tx3 = Transaction(account="Test", lat=40.7128, lon=-74.0060)
        assert tx3.latitude == 40.7128
        assert tx3.longitude == -74.0060

    def test_location_validation_zero_longitude_aliases(self):
        tx1 = Transaction(account="Test", lat=51.5074, long=0)
        assert tx1.longitude == 0

        tx2 = Transaction(account="Test", location={"lat": 51.5074, "lng": 0})
        assert tx2.longitude == 0

    def test_location_validation_dict_object(self):
        """Test location validation with nested location dict"""
        tx = Transaction(account="Test", location={"latitude": 51.5074, "longitude": -0.1278})
        assert tx.latitude == 51.5074
        assert tx.longitude == -0.1278

        tx2 = Transaction(account="Test", location={"lat": 51.5074, "lng": -0.1278})
        assert tx2.latitude == 51.5074
        assert tx2.longitude == -0.1278

    def test_location_validation_string_pair(self):
        """Test location validation with comma-separated string"""
        tx = Transaction(account="Test", location="51.5074, -0.1278")
        assert tx.latitude == 51.5074
        assert tx.longitude == -0.1278

    def test_location_validation_missing_one_coordinate(self):
        """Test that providing only latitude or only longitude raises ValidationError"""
        with pytest.raises(ValidationError):
            Transaction(account="Test", latitude=37.7749)

        with pytest.raises(ValidationError):
            Transaction(account="Test", longitude=-122.4194)

    def test_location_validation_out_of_range(self):
        """Test that out of range coordinates raise ValidationError"""
        with pytest.raises(ValidationError):
            Transaction(account="Test", latitude=95.0, longitude=0.0)

        with pytest.raises(ValidationError):
            Transaction(account="Test", latitude=0.0, longitude=185.0)

    def test_location_validation_invalid_format(self):
        """Test that invalid coordinate strings raise ValidationError"""
        with pytest.raises(ValidationError):
            Transaction(account="Test", latitude="invalid", longitude="0.0")
