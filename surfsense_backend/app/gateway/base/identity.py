"""Gateway identity helpers."""

from __future__ import annotations

import hashlib


def normalize_external_peer_id(value: str | int | None) -> str | None:
    if value is None:
        return None
    return str(value).strip()


def hash_external_id(value: str | int | None) -> str | None:
    normalized = normalize_external_peer_id(value)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

