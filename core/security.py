import random
import string
import time

from fastapi import HTTPException
from fastapi import Security
from fastapi.security.api_key import APIKeyHeader

from core.config import settings

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == settings.api_key:
        return api_key_header
    else:
        raise HTTPException(
            status_code=403,
            detail="Could not validate credentials",
        )


def generate_custom_id():
    timestamp = str(int(time.time()))
    random_chars = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ID-{timestamp}-{random_chars}"
