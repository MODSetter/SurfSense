import base64
import binascii
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# The Keygen account's Ed25519 public key, as the dashboard shows it. Compiled
# in, never read from config or disk. Tests swap it for the fixture key.
# TODO(release): this is the contracts/license-sample TEST key; replace with
# the account key before v1.0.0.
KEYGEN_PUBLIC_KEY_HEX = (
    "26c9700024d49bf40cf51cbc4fe73dd9544597170f5a8682d8166ccd0ad2cbe6"
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

    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(KEYGEN_PUBLIC_KEY_HEX)).verify(
            base64.b64decode(sig), f"license/{enc}".encode()
        )
    except (InvalidSignature, binascii.Error) as failure:
        raise LicenseRejectedError("bad_signature") from failure

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
