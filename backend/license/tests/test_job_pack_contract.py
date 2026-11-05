"""Contract 6's sample pack passes the server's checks and is served byte for byte.

The sample is the contract's, signed by its own test key, so both sides check the
same bytes; `docs/contracts/job-pack-sample/generate.py` writes it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from license.job_packs import signature
from license.job_packs.verify import verified_pack
from license.tests.job_pack_portal import PackPortal

pytestmark = pytest.mark.unit

SAMPLE = Path(__file__).resolve().parents[3] / "docs/contracts/job-pack-sample"
SAMPLE_ZIP = SAMPLE / "sample-jobs-1.0.0.zip"


@pytest.fixture
def sample_key_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    key = (SAMPLE / "public-key.hex").read_text(encoding="ascii").strip()
    monkeypatch.setattr(signature, "PACK_PUBLIC_KEYS_HEX", (key,))


@pytest.fixture
def sample_in_store(pack_portal: PackPortal, sample_key_trusted: None) -> bytes:
    shutil.copyfile(SAMPLE_ZIP, pack_portal.packs / SAMPLE_ZIP.name)
    pack_portal.keygen.add(
        "lic-sample", plan="business", jobs="JOB_QUESTIONNAIRE", expiry=None
    )
    return SAMPLE_ZIP.read_bytes()


def test_the_contract_sample_passes_the_servers_checks(sample_key_trusted) -> None:
    pack = verified_pack(SAMPLE_ZIP.read_bytes(), name=SAMPLE_ZIP.name)

    assert (pack.id, pack.version) == ("sample-jobs", "1.0.0")
    assert [(job.key, job.runner, job.entitlement) for job in pack.jobs] == [
        ("sample-questionnaire", "workbook-rows/1", "JOB_QUESTIONNAIRE")
    ]


async def test_the_route_serves_the_sample_byte_for_byte_from_a_folder(
    pack_portal: PackPortal, sample_in_store: bytes
) -> None:
    reply = await pack_portal.ask("KEY-lic-sample")

    assert reply.status_code == 200
    assert reply.content == sample_in_store
    assert reply.headers["x-job-pack-version"] == "1.0.0"
