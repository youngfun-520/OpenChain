"""API key authentication for OpenChain API."""
import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from typing import Optional

def get_valid_api_keys() -> set[str]:
    """Get set of valid API keys from environment variable."""
    keys_str = os.environ.get("OPENCHAIN_API_KEYS", "")
    if not keys_str:
        return set()
    return {k.strip() for k in keys_str.split(",") if k.strip()}

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Verify the API key from X-API-Key header.

    Returns the API key if valid.
    Raises HTTPException 401 if invalid or missing.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    valid_keys = get_valid_api_keys()
    if api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key