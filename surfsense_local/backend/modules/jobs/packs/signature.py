"""Who made a pack: its manifest, which lists every file's sha256, signed with SurfSense's
Ed25519 pack key. Only the public halves are here; the private key and the script that signs
with it live with the packs' own content, outside this repository.
"""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from modules.jobs.packs.manifest import SIGNATURE, PackRefusedError

# Raw 32-byte keys in hex, never read from config or disk. A tuple so a release can trust an
# old and a new key while the signing key is rotated. Newest first.
PACK_PUBLIC_KEYS_HEX = (
    "1545536e7caeffd794d26d01cfc22e5ef01d07ddf10894dfe517c2d6afdb9230",  # pragma: allowlist secret
)

# Signed before the manifest, so a signature made for anything else never passes for a pack's.
DOMAIN = b"surfsense-job-pack/1\n"
# One line per key that signed the pack, so a rotation can sign with the old key and the new.
MAX_SIGNATURE_LINES = 8
_SIGNATURE_BYTES = 64


def signed_payload(manifest: object) -> bytes:
    """The bytes a pack's signature covers: its manifest as canonical JSON, so a line ending or
    an indent changes nothing, while any name, version, file or sha256 does."""
    canonical = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return DOMAIN + canonical.encode("utf-8")


def check_signature(folder: Path, manifest: object) -> None:
    """Refuse a pack that SurfSense did not sign, or that changed after it did: one line of its
    signature made by a key this app trusts is enough. `manifest` is the manifest as the caller
    read it, once, so the copy checked is the copy used."""
    path = folder / SIGNATURE
    if not path.is_file():
        raise PackRefusedError(
            "PACK_NOT_SIGNED",
            "The pack is not signed by SurfSense, so the app does not run it.",
        )
    try:
        signatures = _signature_lines(path.read_bytes())
        # A manifest that cannot be put in signed form, such as one holding a lone surrogate,
        # is one no key signed.
        payload = signed_payload(manifest)
    except (OSError, ValueError, TypeError, RecursionError, binascii.Error) as broken:
        raise PackRefusedError(
            "PACK_BAD_SIGNATURE", "The pack's signature cannot be read."
        ) from broken
    if not any(signed_by_pack_key(payload, signature) for signature in signatures):
        raise PackRefusedError(
            "PACK_BAD_SIGNATURE",
            "The pack's signature does not match it: it changed after SurfSense signed it, "
            "or SurfSense did not sign it.",
        )


def signed_by_pack_key(payload: bytes, signature: bytes) -> bool:
    for key_hex in PACK_PUBLIC_KEYS_HEX:
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex)).verify(
                signature, payload
            )
            return True
        except (InvalidSignature, ValueError):
            continue
    return False


def _signature_lines(raw: bytes) -> list[bytes]:
    """Each line's signature, the line its standard base64 alone, as the licence server reads
    it; blank lines and the last newline count for nothing."""
    lines = [line for line in raw.splitlines() if line.strip()]
    if not 1 <= len(lines) <= MAX_SIGNATURE_LINES:
        raise ValueError(f"{len(lines)} signature lines")
    signatures = [base64.b64decode(line, validate=True) for line in lines]
    if any(len(signature) != _SIGNATURE_BYTES for signature in signatures):
        raise ValueError("a signature line is not one Ed25519 signature")
    return signatures
