from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from core.security import get_api_key
from models.transaction import Transaction
from services.actual_service import actual_service

router = APIRouter()


@router.post("/", dependencies=[Depends(get_api_key)])
def add_transaction(transaction: Transaction):
    try:
        actual_service.add_transaction(
            account=transaction.account,
            amount=transaction.amount * Decimal(-1),
            date=transaction.date,
            payee=transaction.payee,
            notes=transaction.notes,
            cleared=transaction.cleared,
        )
        return {"message": "Transaction added successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
