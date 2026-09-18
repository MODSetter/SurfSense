import base64
import binascii
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# The Keygen account's Ed25519 public keys, as the dashboard shows them. Compiled
# in, never read from config or disk. Tests swap them for the fixture key.
#
# A tuple around one key: a file signed by any listed key is accepted, so
# replacing the account key is a release that trusts both rather than a recall
# that invalidates every license already issued. Newest first.
KEYGEN_PUBLIC_KEYS_HEX = (
    "cef8ffb796122d0126d29e6db03df39305417d4fe271bc234a9bc62f0521c41e",
)

# A laptop clock a few minutes fast is not tampering; keygen-go uses the same.
MAX_CLOCK_DRIFT = timedelta(minutes=5)

_PEM_MARKERS = re.compile(r"-----(BEGIN|END) LICENSE FILE-----")


class LicenseRejectedError(Exception):
    """A file the app will not keep; `code` is one of the contract's reasons."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Verified:
    key: str
    plan: str
    email: str
    expiry: datetime
    max_users: int | None
    issued: datetime


def verify(certificate: str, now: datetime) -> Verified:
    """Contract 1 consumer steps, in order, stopping at the first failure."""
    try:
        body = base64.b64decode(re.sub(r"\s+", "", _PEM_MARKERS.sub("", certificate)))
        outer = json.loads(body)
        enc, sig, alg = outer["enc"], outer["sig"], outer["alg"]
    except (binascii.Error, UnicodeDecodeError, ValueError, KeyError, TypeError) as e:
        raise LicenseRejectedError("not_a_license_file") from e

    if alg != "base64+ed25519":
        raise LicenseRejectedError("unsupported_algorithm")

    for key_hex in KEYGEN_PUBLIC_KEYS_HEX:
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex)).verify(
                base64.b64decode(sig), f"license/{enc}".encode()
            )
            break
        except (InvalidSignature, binascii.Error):
            continue
    else:
        raise LicenseRejectedError("bad_signature")

    payload = json.loads(base64.b64decode(enc))
    meta, attributes = payload["meta"], payload["data"]["attributes"]

    if _instant(meta["issued"]) > now + MAX_CLOCK_DRIFT:
        raise LicenseRejectedError("clock_untrusted")
    if meta["expiry"] is not None and _instant(meta["expiry"]) < now:
        raise LicenseRejectedError("file_expired")

    return Verified(
        key=attributes["key"],
        plan=attributes["metadata"]["plan"],
        email=attributes["metadata"]["email"],
        expiry=_instant(attributes["expiry"]),
        max_users=attributes["maxUsers"],
        issued=_instant(meta["issued"]),
    )


def _instant(iso: str) -> datetime:
    parsed = datetime.fromisoformat(iso)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
