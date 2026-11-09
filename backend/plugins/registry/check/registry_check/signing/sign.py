"""Stamps and signs the registry; the private key lives only in a CI secret."""

import base64
import binascii
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from registry_check.signing.signed_bytes import registry_bytes


def sign_registry(
    source_path: Path,
    published_dir: Path,
    private_key_b64: str,
    now: datetime | None = None,
) -> None:
    """Writes the stamped list and its .sig into `published_dir`; the source stays as written.

    The .sig is the bare base64 signature, with no newline.
    """
    key = _private_key(private_key_b64)
    registry = json.loads(source_path.read_text(encoding="utf-8"))
    stamped = _stamped(registry, source_path.parent / "icons", now or datetime.now(UTC))
    content = registry_bytes(stamped)
    published_dir.mkdir(parents=True, exist_ok=True)
    published = published_dir / source_path.name
    published.write_bytes(content)
    signature = base64.b64encode(key.sign(content))
    published.with_name(f"{published.name}.sig").write_bytes(signature)


def _stamped(
    registry: dict[str, Any], icons_dir: Path, now: datetime
) -> dict[str, Any]:
    # The app ignores a list older than its cached copy, so the date must be honest.
    generated_at = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    rest = {
        k: v for k, v in registry.items() if k not in {"schema_version", "generated_at"}
    }
    for entry in rest.get("plugins", []):
        entry.pop("icon_sha256", None)
        if entry.get("icon"):
            digest = hashlib.sha256((icons_dir / entry["icon"]).read_bytes())
            entry["icon_sha256"] = digest.hexdigest()
    return {
        "schema_version": registry["schema_version"],
        "generated_at": generated_at,
        **rest,
    }


def _private_key(private_key_b64: str) -> Ed25519PrivateKey:
    try:
        raw = base64.b64decode(private_key_b64.strip(), validate=True)
    except binascii.Error as error:
        raise ValueError("the signing key must be base64") from error
    if len(raw) != 32:
        raise ValueError("the signing key must be the raw 32-byte Ed25519 private key")
    return Ed25519PrivateKey.from_private_bytes(raw)
