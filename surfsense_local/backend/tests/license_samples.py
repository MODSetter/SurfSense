"""The contract's sample license files, verified as a shipped app would on a day they are valid."""

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient

from modules.license import service, verify

SAMPLE = Path(__file__).resolve().parents[3] / "docs/contracts/license-sample"
# The fixtures were issued 2026-09-10 and the shortest one expires two weeks later.
TODAY = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
# The keys inside the sample files.
INDIVIDUAL_KEY = "TEST-INDV-2026-0001"
TRIAL_KEY = "TEST-TRIL-2026-0003"
BUSINESS_KEY = "TEST-BUSN-2026-0005"

# generate.mjs's fixed seed, so a test can sign a payload the fixtures lack.
TEST_SEED = b"surfsense-contract-1-test-seed!!"


def trust_sample_licenses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify with the samples' public key, on a day they are all valid."""
    monkeypatch.setattr(
        verify,
        "KEYGEN_PUBLIC_KEYS_HEX",
        ((SAMPLE / "public-key.hex").read_text().strip(),),
    )
    monkeypatch.setattr(service, "now", lambda: TODAY)


async def import_license(client: AsyncClient, file: str) -> None:
    """Import a sample file, as Settings > License does."""
    imported = await client.put(
        "/license", json={"certificate": (SAMPLE / file).read_text()}
    )
    assert imported.status_code == 200, imported.text


def signed(payload: dict, alg: str = "base64+ed25519") -> str:
    """A certificate over `payload`, signed the way Keygen signs."""
    enc = base64.b64encode(json.dumps(payload).encode()).decode()
    sig = Ed25519PrivateKey.from_private_bytes(TEST_SEED).sign(
        f"license/{enc}".encode()
    )
    outer = {"enc": enc, "sig": base64.b64encode(sig).decode(), "alg": alg}
    wrapped = base64.b64encode(json.dumps(outer).encode()).decode()
    return f"-----BEGIN LICENSE FILE-----\n{wrapped}\n-----END LICENSE FILE-----\n"


def business_license(
    *,
    key: str = BUSINESS_KEY,
    expiry: str = "2027-10-10T00:00:00.000Z",
    issued: str = "2026-09-10T00:00:00.000Z",
    max_users: int | None = 5,
    **metadata: str | None,
) -> str:
    """The contract's Business sample, business.lic: five people at a firm, with the
    questionnaire job. A metadata field passed as None is left out."""
    fields = {
        "plan": "business",
        "email": "partner@example.com",
        "firm": "Example Accounting LLP",
        "jobs": "JOB_QUESTIONNAIRE",
        **metadata,
    }
    return signed(
        {
            "meta": {"issued": issued, "expiry": None, "ttl": None},
            "data": {
                "attributes": {
                    "key": key,
                    "expiry": expiry,
                    "maxUsers": max_users,
                    "metadata": {k: v for k, v in fields.items() if v is not None},
                }
            },
        }
    )
