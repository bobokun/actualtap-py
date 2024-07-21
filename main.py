from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException

from api import transactions
from core.config import redact_sensitive_settings
from core.security import get_api_key
from services.actual_service import actual_service

app = FastAPI()

app.include_router(transactions.router, prefix="/transactions", tags=["transactions"], dependencies=[Depends(get_api_key)])


@app.get("/", dependencies=[Depends(get_api_key)])
def read_root():
    return {"message": "Welcome to the ActualTap API"}


@app.get("/settings", dependencies=[Depends(get_api_key)])
def get_settings():
    keys_to_remove = ["api_key", "actual_password"]  # List the keys to remove
    filtered_settings = redact_sensitive_settings(keys_to_remove)
    return filtered_settings


@app.get("/login", dependencies=[Depends(get_api_key)])
def login():
    try:
        actual_service.login()
        return {"message": "Login Successful"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
