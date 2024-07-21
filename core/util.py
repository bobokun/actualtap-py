from datetime import date
from datetime import datetime


def convert_to_date(date_str: str) -> date:
    # Define the format of the input date string
    date_format = "%b %d, %Y"

    # Parse the date string into a datetime object
    datetime_obj = datetime.strptime(date_str, date_format)

    # Extract and return the date part
    return datetime_obj.date()
