import json

from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.exception_handlers import (
    http_exception_handler as default_http_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_redoc_html
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from api import transactions
from core.config import redact_sensitive_settings
from core.logs import MyLogger
from core.security import get_api_key

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.include_router(transactions.router, prefix="", tags=["transactions"], dependencies=[Depends(get_api_key)])
logger = MyLogger()


@app.get("/", dependencies=[Depends(get_api_key)])
def read_root():
    return {"message": "Welcome to the ActualTap API"}


@app.get("/settings", dependencies=[Depends(get_api_key)])
def get_settings():
    keys_to_remove = ["api_key", "actual_password"]  # List the keys to remove
    filtered_settings = redact_sensitive_settings(keys_to_remove)
    return filtered_settings


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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error for request {request.method} {request.url}:\n{json.dumps(exc.errors(), indent=2)}")
    logger.error(f"Request body: {json.dumps(await request.json(), indent=2)}")

    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": await request.json()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Log the details of the bad request
    if exc.status_code == 400 or exc.status_code == 500:
        logger.error(f"Validation error for request {request.method} {request.url}:\n{json.dumps(exc.detail, indent=2)}")
        logger.error(f"Request body: {json.dumps(await request.json(), indent=2)}")

    # Return the default HTTP exception response
    return await default_http_exception_handler(request, exc)
