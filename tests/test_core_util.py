from datetime import date
from datetime import datetime

import pytest

from core.util import convert_to_date


class TestCoreUtil:
    """Test core utility functions"""

    def test_convert_to_date_datetime_input(self):
        """Test convert_to_date with datetime input"""
        test_datetime = datetime(2024, 1, 15, 14, 30, 45)
        result = convert_to_date(test_datetime)
        assert isinstance(result, date)
        assert result == date(2024, 1, 15)

    def test_convert_to_date_iso_format(self):
        """Test convert_to_date with ISO format string"""
        result = convert_to_date("2024-01-15")
        assert isinstance(result, date)
        assert result == date(2024, 1, 15)

    def test_convert_to_date_mmm_dd_yyyy_format(self):
        """Test convert_to_date with 'MMM DD, YYYY' format"""
        result = convert_to_date("Jan 15, 2024")
        assert isinstance(result, date)
        assert result == date(2024, 1, 15)

    def test_convert_to_date_mmm_dd_yyyy_no_comma_format(self):
        """Test convert_to_date with 'MMM DD YYYY' format (no comma)"""
        result = convert_to_date("Jan 15 2024")
        assert isinstance(result, date)
        assert result == date(2024, 1, 15)

    def test_convert_to_date_dd_mmm_yyyy_format(self):
        """Test convert_to_date with 'DD MMM YYYY' format"""
        result = convert_to_date("15 Jan 2024")
        assert isinstance(result, date)
        assert result == date(2024, 1, 15)

    def test_convert_to_date_various_months(self):
        """Test convert_to_date with different month abbreviations"""
        test_cases = [
            ("Feb 28, 2024", date(2024, 2, 28)),
            ("Mar 15, 2024", date(2024, 3, 15)),
            ("Apr 10, 2024", date(2024, 4, 10)),
            ("May 05, 2024", date(2024, 5, 5)),
            ("Jun 20, 2024", date(2024, 6, 20)),
            ("Jul 04, 2024", date(2024, 7, 4)),
            ("Aug 31, 2024", date(2024, 8, 31)),
            ("Sep 15, 2024", date(2024, 9, 15)),
            ("Oct 31, 2024", date(2024, 10, 31)),
            ("Nov 25, 2024", date(2024, 11, 25)),
            ("Dec 25, 2024", date(2024, 12, 25)),
        ]

        for date_string, expected_date in test_cases:
            result = convert_to_date(date_string)
            assert result == expected_date, f"Failed for {date_string}"

    def test_convert_to_date_leap_year(self):
        """Test convert_to_date with leap year date"""
        result = convert_to_date("2024-02-29")
        assert result == date(2024, 2, 29)

    def test_convert_to_date_invalid_format(self):
        """Test convert_to_date with invalid format"""
        with pytest.raises(ValueError) as exc_info:
            convert_to_date("invalid-date-format")

        error_message = str(exc_info.value)
        assert "Invalid date format" in error_message
        assert "YYYY-MM-DD" in error_message
        assert "MMM DD, YYYY" in error_message

    def test_convert_to_date_invalid_date_values(self):
        """Test convert_to_date with invalid date values"""
        invalid_dates = [
            "2024-13-01",  # Invalid month
            "2024-02-30",  # Invalid day for February
            "2023-02-29",  # Invalid leap year date
            "2024-04-31",  # Invalid day for April
        ]

        for invalid_date in invalid_dates:
            with pytest.raises(ValueError):
                convert_to_date(invalid_date)

    def test_convert_to_date_empty_string(self):
        """Test convert_to_date with empty string"""
        with pytest.raises(ValueError):
            convert_to_date("")

    def test_convert_to_date_partial_formats(self):
        """Test convert_to_date with partial date formats"""
        invalid_partial_dates = [
            "2024-01",  # Missing day
            "Jan 2024",  # Missing day
            "15, 2024",  # Missing month
        ]

        for partial_date in invalid_partial_dates:
            with pytest.raises(ValueError):
                convert_to_date(partial_date)

    def test_convert_to_date_case_sensitivity(self):
        """Test convert_to_date with different cases"""
        # Should work with proper case
        result1 = convert_to_date("Jan 15, 2024")
        assert result1 == date(2024, 1, 15)

        # Python's strptime is actually case-insensitive for month abbreviations
        # These should also work
        result2 = convert_to_date("jan 15, 2024")  # lowercase month
        assert result2 == date(2024, 1, 15)

        result3 = convert_to_date("JAN 15, 2024")  # uppercase month
        assert result3 == date(2024, 1, 15)
