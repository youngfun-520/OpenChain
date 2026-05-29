"""API key authentication for OpenChain API."""
import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class APIKey:
    """API key with metadata."""
    label: str
    key: str
    scopes: set[str]
    created_at: datetime

def _parse_keys() -> dict[str, APIKey]:
    """Parse OPENCHAIN_API_KEYS env var.

    Format: "key1:scope1,scope2|key2:scope1|key3"
    If no scopes specified, key grants no scoped access.
    """
    keys_str = os.environ.get("OPENCHAIN_API_KEYS", "")
    if not keys_str:
        return {}
    result = {}
    for entry in keys_str.split("|"):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            label, scopes_str = entry.split(":", 1)
            key = label  # key value = label for simple keys
            scopes = {s.strip() for s in scopes_str.split(",") if s.strip()}
        else:
            label = entry
            key = entry
            scopes = set()
        result[label] = APIKey(label=label, key=key, scopes=scopes, created_at=datetime.now())
    return result

def get_valid_api_keys() -> dict[str, APIKey]:
    """Get dict of valid API keys from environment variable."""
    return _parse_keys()

def get_key_by_label(label: str) -> Optional[APIKey]:
    """Get APIKey by its label."""
    keys = get_valid_api_keys()
    return keys.get(label)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Verify the API key from X-API-Key header.

    Returns the API key label if valid.
    Raises HTTPException 401 if invalid or missing.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    keys = get_valid_api_keys()
    # Check if api_key matches any key's value
    for label, key_obj in keys.items():
        if key_obj.key == api_key:
            return label

    raise HTTPException(status_code=401, detail="Invalid API key")

def require_scope(required_scope: str):
    """Dependency factory that requires a specific scope."""
    async def scope_checker(api_key_label: str = Security(verify_api_key)) -> str:
        keys = get_valid_api_keys()
        key_obj = keys.get(api_key_label)
        if not key_obj:
            raise HTTPException(status_code=401, detail="Invalid API key")
        if "admin" in key_obj.scopes:
            return api_key_label
        if required_scope not in key_obj.scopes:
            raise HTTPException(status_code=403, detail=f"Missing required scope: {required_scope}")
        return api_key_label
    return scope_checker