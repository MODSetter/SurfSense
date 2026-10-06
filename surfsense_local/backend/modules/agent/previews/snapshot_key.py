"""The key Electron presents when it takes and answers Word snapshot requests.

Loopback is open to every process on the machine, and one that is not a browser
sends no Origin. Without this, any of them could take a snapshot request and
post the pages the agent checks its work against. Electron makes the key at
launch and hands it to the API alone.
"""

import hmac
from functools import lru_cache

from fastapi import HTTPException, Request, status
from pydantic_settings import BaseSettings, SettingsConfigDict


class SnapshotKeySettings(BaseSettings):
    """Unset when Electron did not start this API: then no caller holds the key."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    docx_snapshot_key: str | None = None


@lru_cache
def get_snapshot_key_settings() -> SnapshotKeySettings:
    """Cached so the environment is parsed once, not per poll."""
    return SnapshotKeySettings()


def require_snapshot_key(request: Request) -> None:
    """Refuse a caller that does not hold the key Electron gave this API."""
    key = get_snapshot_key_settings().docx_snapshot_key
    presented = request.headers.get("authorization", "").encode()
    if not key or not hmac.compare_digest(presented, f"Bearer {key}".encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "the desktop app's snapshot key is required"
        )
