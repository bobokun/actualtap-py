from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class Transaction(BaseModel):
    account: str = ""
    amount: Optional[Decimal] = Field(default=Decimal(0), decimal_places=2)
    date: Optional[str] = datetime.now().strftime("%b %d, %Y")
    payee: Optional[str] = ""
    notes: Optional[str] = ""
    cleared: Optional[bool] = False

    @field_validator("amount")
    def empty_str_to_zero(cls, v):
        if v == "":
            return Decimal(0)
        return v
