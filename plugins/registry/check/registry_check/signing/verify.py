"""Checks the registry as the app will: the exact bytes against `<list>.sig` and a public key."""

import base64
import binascii
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def verify_registry(registry_path: Path, public_key_hex: str) -> bool:
    key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
    signature_path = registry_path.with_name(f"{registry_path.name}.sig")
    if not signature_path.is_file():
        return False
    try:
        signature = base64.b64decode(signature_path.read_bytes().strip(), validate=True)
        key.verify(signature, registry_path.read_bytes())
    except (InvalidSignature, binascii.Error, ValueError):
        return False
    return True
