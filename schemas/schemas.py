from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class TransactionBase(BaseModel):
    account: str = Field(..., description="Account name is required")
    amount: Decimal = Field(..., description="Transaction amount is required")
    date: datetime = Field(..., description="Transaction date is required")
    payee: Optional[str] = None
    notes: Optional[str] = None
    cleared: Optional[bool] = False


class Transaction(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    pass
