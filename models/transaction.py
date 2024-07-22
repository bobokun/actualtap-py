from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from pydantic import validator


class Transaction(BaseModel):
    account: str = ""
    amount: Optional[float] = 0
    date: Optional[str] = datetime.now().strftime("%b %d, %Y")
    payee: Optional[str] = ""
    notes: Optional[str] = ""
    cleared: Optional[bool] = False

    @validator("amount", pre=True)
    def empty_str_to_zero(cls, v):
        if v == "":
            return 0
        return v
