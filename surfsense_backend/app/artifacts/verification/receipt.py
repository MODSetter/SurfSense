"""Content-bound, signed verification receipts."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from typing import Any, Literal
from weakref import WeakValueDictionary

from pydantic import BaseModel, ConfigDict, ValidationError

from app.sandbox import SandboxSession

RECEIPT_PREFIX = "/tmp/.surfsense-artifact-verification-"
PREVIEW_PREFIX = "/tmp/.surfsense-artifact-preview-"
RECEIPT_MAX_AGE_SECONDS = 15 * 60
_PATH_LOCKS: WeakValueDictionary[tuple[str, str], asyncio.Lock] = WeakValueDictionary()


class VerificationReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    workspace_id: int
    session_id: str
    format: str
    primary_path: str
    primary_sha256: str
    markdown_representation_sha256: str | None = None
    preview_path: str | None = None
    preview_sha256: str | None = None
    page_count: int | None = None
    visual: Literal["clean", "unavailable", "not_required"]
    unavailable_reason: str | None = None
    provenance: dict[str, Any] | None = None
    issued_at: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def receipt_path(primary_path: str) -> str:
    """Return the isolated receipt path for one sandbox artifact path."""
    path_digest = hashlib.sha256(primary_path.encode()).hexdigest()
    return f"{RECEIPT_PREFIX}{path_digest}.json"


def preview_path(primary_path: str) -> str:
    """Return the stable staged-preview path for one sandbox artifact path."""
    path_digest = hashlib.sha256(primary_path.encode()).hexdigest()
    return f"{PREVIEW_PREFIX}{path_digest}.pdf"


def artifact_path_lock(session_id: str, primary_path: str) -> asyncio.Lock:
    """Serialize verification and promotion for one sandbox output path."""
    key = (session_id, primary_path)
    lock = _PATH_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _PATH_LOCKS[key] = lock
    return lock


def _payload_bytes(payload: VerificationReceipt | dict[str, object]) -> bytes:
    return json.dumps(
        payload.model_dump(mode="json")
        if isinstance(payload, VerificationReceipt)
        else payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _signature(
    payload: VerificationReceipt | dict[str, object], secret_key: str
) -> str:
    if not secret_key:
        raise ValueError("SECRET_KEY is required for artifact verification")
    return hmac.new(
        secret_key.encode(), _payload_bytes(payload), hashlib.sha256
    ).hexdigest()


async def write_receipt(
    session: SandboxSession,
    receipt: VerificationReceipt,
    secret_key: str,
) -> None:
    envelope = {
        "payload": receipt.model_dump(mode="json"),
        "signature": _signature(receipt, secret_key),
    }
    await session.write_file(
        receipt_path(receipt.primary_path),
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode(),
    )


async def read_receipt(
    session: SandboxSession,
    secret_key: str,
    *,
    workspace_id: int,
    primary_path: str,
    now: int | None = None,
    allow_expired: bool = False,
) -> VerificationReceipt:
    try:
        data = await session.read_file(receipt_path(primary_path))
    except (FileNotFoundError, KeyError):
        raise ValueError("Verify this file again before presenting it") from None
    if not data:
        raise ValueError("Verify this file again before presenting it")
    try:
        envelope = json.loads(data.decode())
        if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
            raise ValueError
        payload = envelope["payload"]
        receipt = VerificationReceipt.model_validate(payload)
        signature = envelope["signature"]
    except (KeyError, TypeError, UnicodeDecodeError, ValidationError, ValueError):
        raise ValueError("Artifact verification receipt is unreadable") from None

    if not isinstance(signature, str) or not hmac.compare_digest(
        signature, _signature(payload, secret_key)
    ):
        raise ValueError("Artifact verification receipt has an invalid signature")
    if receipt.workspace_id != workspace_id or receipt.session_id != session.session_id:
        raise ValueError(
            "Artifact verification receipt belongs to another workspace or sandbox"
        )

    if not allow_expired:
        age = (int(time.time()) if now is None else now) - receipt.issued_at
        if age < 0 or age > RECEIPT_MAX_AGE_SECONDS:
            raise ValueError("Artifact verification receipt has expired")
    return receipt
