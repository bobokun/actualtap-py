import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from core.util import convert_to_date


class Transaction(BaseModel):
    account: str = Field(..., description="Account name or ID is required")
    amount: Decimal = Field(default=Decimal(0), description="Transaction amount")
    date: datetime.date = Field(
        default_factory=datetime.date.today,
        description="Transaction date in formats: YYYY-MM-DD, MMM DD, YYYY, or MMM DD YYYY",
    )
    payee: Optional[str] = None
    notes: Optional[str] = None
    cleared: bool = False

    @field_validator("amount", mode="before")
    def validate_amount(cls, v):
        try:
            # Replace comma with period if present
            if isinstance(v, str) and "," in v:
                v = v.replace(",", ".")
            return Decimal(str(v)) if v else Decimal(0)
        except Exception:
            raise ValueError("Invalid amount format. Must be a valid decimal number.")

    @field_validator("date", mode="before")
    def parse_date(cls, value):
        try:
            parsed_date = convert_to_date(value)
            # If convert_to_date returns a datetime object convert it to a date object
            if isinstance(parsed_date, datetime.datetime):
                return parsed_date.date()
            return parsed_date
        except ValueError as e:
            raise ValueError(str(e))
