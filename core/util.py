from datetime import date, datetime
from typing import Union


def convert_to_date(date_input: Union[str, datetime]) -> date:
    if isinstance(date_input, datetime):
        return date_input.date()

    # Try different date formats
    date_formats = [
        "%Y-%m-%d",  # 2024-11-25 (ISO format)
        "%b %d, %Y",  # Nov 25, 2024
        "%b %d %Y",  # Nov 25 2024
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
    )
