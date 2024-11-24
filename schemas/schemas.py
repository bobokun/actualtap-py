from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, validator


class TransactionBase(BaseModel):
    account: str = Field(..., description="Account name is required")
    amount: Decimal = Field(..., description="Transaction amount is required")
    date: datetime = Field(
        ...,
        description="Transaction date is required in formats: YYYY-MM-DD or MMM DD, YYYY or MMM DD YYYY",
    )
    payee: Optional[str] = None
    notes: Optional[str] = None
    cleared: Optional[bool] = False

    @validator("date", pre=True)
    def parse_date(cls, value):
        if isinstance(value, datetime):
            return value

        date_formats = [
            "%Y-%m-%d",  # 2024-11-25 (ISO format)
            "%b %d, %Y",  # Nov 25, 2024
            "%b %d %Y",  # Nov 25 2024
        ]

        for date_format in date_formats:
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue

        raise ValueError(
            "Invalid date format. Accepted formats:\n"
            "- YYYY-MM-DD (e.g. 2024-11-25)\n"
            "- MMM DD, YYYY (e.g. Nov 25, 2024)\n"
            "- MMM DD YYYY (e.g. Nov 25 2024)"
        )


class Transaction(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    pass
