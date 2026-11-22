"""The registry's Ed25519 public keys, compiled in, and whether a list was signed by one."""

import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Raw 32-byte keys in hex, never read from config or disk. A tuple so a release can
# trust an old and a new key while CI's signing key is rotated. Newest first.
REGISTRY_PUBLIC_KEYS_HEX = (
    "9498a1606105a625feeaa655648df03885410421a387478a72ec763188f10395",  # pragma: allowlist secret
)


def signed_by_registry(body: bytes, signature_b64: bytes) -> bool:
    try:
        signature = base64.b64decode(signature_b64.strip(), validate=True)
    except (binascii.Error, ValueError):
        return False
    for key_hex in REGISTRY_PUBLIC_KEYS_HEX:
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex)).verify(
                signature, body
            )
            return True
        except (InvalidSignature, ValueError):
            continue
    return False
