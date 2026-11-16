"""Who made a pack: its manifest signed with SurfSense's Ed25519 pack keys, one signature a line.

The app accepts a pack when any line verifies; the server serves it only when every
line does, so nothing it serves is refused by an app that trusts any of its keys.
"""

from __future__ import annotations

import base64
import binascii
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from license.job_packs.manifest import PackRefusedError

# The app's list (its PACK_PUBLIC_KEYS_HEX), newest first: both change together.
# Raw 32-byte keys in hex, never read from configuration.
PACK_PUBLIC_KEYS_HEX = (
    "1545536e7caeffd794d26d01cfc22e5ef01d07ddf10894dfe517c2d6afdb9230",  # pragma: allowlist secret
)

# Signed before the manifest, so a signature made for anything else never passes for a pack's.
DOMAIN = b"surfsense-job-pack/1\n"
# Room for a rotation's old and new keys, and more, without an unbounded file.
_MAX_LINES = 8
_SIGNATURE_BYTES = 64


def signed_payload(manifest: object) -> bytes:
    """The bytes a pack's signature covers, byte-identical to the app's: the manifest as
    canonical JSON, so an indent or a line ending changes nothing."""
    canonical = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return DOMAIN + canonical.encode("utf-8")


def signature_lines(raw: bytes) -> list[bytes]:
    """The signatures in `job-pack.sig`, one a line; blank lines and a final newline ignored."""
    lines = [line for line in raw.splitlines() if line.strip()]
    if not 1 <= len(lines) <= _MAX_LINES:
        raise PackRefusedError(
            "PACK_BAD_SIGNATURE",
            f"job-pack.sig holds {len(lines)} signatures; a pack has 1 to {_MAX_LINES}.",
        )
    signatures = []
    for line in lines:
        try:
            signature = base64.b64decode(line, validate=True)
        except binascii.Error as broken:
            raise PackRefusedError(
                "PACK_BAD_SIGNATURE", "The pack's signature cannot be read."
            ) from broken
        if len(signature) != _SIGNATURE_BYTES:
            raise PackRefusedError(
                "PACK_BAD_SIGNATURE", "The pack's signature cannot be read."
            )
        signatures.append(signature)
    return signatures


def signed_by_every_line(payload: bytes, signatures: list[bytes]) -> bool:
    """Whether each signature verifies with one of the compiled keys, read at call time."""
    keys = [
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex))
        for key_hex in PACK_PUBLIC_KEYS_HEX
    ]
    return bool(signatures) and all(
        any(_verifies(key, signature, payload) for key in keys)
        for signature in signatures
    )


def _verifies(key: Ed25519PublicKey, signature: bytes, payload: bytes) -> bool:
    try:
        key.verify(signature, payload)
    except InvalidSignature:
        return False
    return True
