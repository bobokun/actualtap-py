from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.openapi.docs import get_redoc_html
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from api import transactions
from core.config import redact_sensitive_settings
from core.security import get_api_key
from services.actual_service import actual_service

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

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


# Override the /docs endpoint
@app.get("/docs", include_in_schema=False, dependencies=[Depends(get_api_key)])
async def get_documentation():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")


# Override the /redoc endpoint
@app.get("/redoc", include_in_schema=False, dependencies=[Depends(get_api_key)])
async def get_redoc():
    return get_redoc_html(openapi_url="/openapi.json", title="redoc")


# Override the /openapi.json endpoint to secure access to the OpenAPI schema itself
@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(get_api_key)])
async def openapi():
    return get_openapi(title="FastAPI", version="1.0.0", routes=app.routes)
