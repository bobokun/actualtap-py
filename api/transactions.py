from decimal import Decimal
from typing import List
from typing import Union

from fastapi import APIRouter
from fastapi import HTTPException

from schemas.transactions import Transaction
from services.actual_service import actual_service

router = APIRouter()


@router.post("/transactions")
@router.post("/transactions/")
def add_transactions(transactions: Union[List[Transaction], Transaction]):
    # check if there is a body
    if not transactions:
        raise HTTPException(status_code=400, detail="No transactions provided")

    # if a single transaction is provided, convert it to a list
    if not isinstance(transactions, list):
        transactions = [transactions]

    try:
        for transaction in transactions:
            transaction.amount *= Decimal(-1)  # Invert the amount

        actual_service.add_transactions(transactions)

        return {"message": "Transactions added successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
