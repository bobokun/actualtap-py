import math
from datetime import date
from datetime import datetime
from typing import Union


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in meters using the Haversine formula."""
    r = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


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
