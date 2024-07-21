from pydantic import BaseModel


class Transaction(BaseModel):
    account: str
    amount: float
    date: str
    payee: str
    notes: str = None
    cleared: bool = False
