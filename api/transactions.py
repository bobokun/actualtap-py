from decimal import Decimal
from typing import List

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from core.security import get_api_key

# from models.transaction import Transaction
from schemas.schemas import Transaction
from services.actual_service import actual_service

router = APIRouter()


@router.post("/transactions", dependencies=[Depends(get_api_key)])
@router.post("/transactions/", dependencies=[Depends(get_api_key)])
def add_transactions(transactions: List[Transaction]):
    # check if there is a body
    if not transactions:
        raise HTTPException(status_code=400, detail="No transactions provided")
    try:
        # Remove this check since FastAPI already ensures we get a list
        # if isinstance(transactions, Transaction):
        #     transactions = [transactions]

        for transaction in transactions:
            transaction.amount *= Decimal(-1)  # Invert the amount

        actual_service.add_transactions(transactions)

        return {"message": "Transactions added successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
