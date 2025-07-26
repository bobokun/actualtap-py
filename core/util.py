from datetime import date
from datetime import datetime
from typing import Union


def convert_to_date(date_input: Union[str, datetime, date]) -> date:
    if isinstance(date_input, datetime):
        return date_input.date()

    if isinstance(date_input, date):
        return date_input

    # Ensure we have a string for parsing
    if not isinstance(date_input, str):
        raise TypeError(f"Expected str, datetime, or date, got {type(date_input).__name__}")

    # Try different date formats
    date_formats = [
        "%Y-%m-%d",  # 2024-11-25 (ISO format)
        "%b %d, %Y",  # Nov 25, 2024
        "%b %d %Y",  # Nov 25 2024
        "%d %b %Y",  # 25 Nov 2024
    ]

    for date_format in date_formats:
        try:
            datetime_obj = datetime.strptime(date_input, date_format)
            return datetime_obj.date()
        except ValueError:
            continue

    # If none of the formats worked, raise an error with examples
    raise ValueError(
        "Invalid date format. Accepted formats:\n"
        "- YYYY-MM-DD (e.g. 2024-11-25)\n"
        "- MMM DD, YYYY (e.g. Nov 25, 2024)\n"
        "- MMM DD YYYY (e.g. Nov 25 2024)\n"
        "- DD MMM YYYY (e.g. 25 Nov 2024)"
    )
