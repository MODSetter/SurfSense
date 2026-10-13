"""The contract's sample license files, verified as a shipped app would on a day they are valid."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient

from modules.license import service, verify

SAMPLE = Path(__file__).resolve().parents[3] / "docs/contracts/license-sample"
# The fixtures were issued 2026-09-10 and the shortest one expires two weeks later.
TODAY = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
# The keys inside the sample files.
INDIVIDUAL_KEY = "TEST-INDV-2026-0001"
TRIAL_KEY = "TEST-TRIL-2026-0003"


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
