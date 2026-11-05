"""Contract 6's sample pack installs with the sample's own key trusted, and with the shipped keys
alone it is refused: the app checks the very bytes the license server's tests check.

The sample comes in docs/contracts/job-pack-sample/ with contract 6 itself, in the license
server's pull request, so these tests skip only while contract 6 is not in this repository.
"""

import shutil
from pathlib import Path

import pytest

from modules.jobs.packs import signature
from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import installed_packs
from modules.jobs.packs.manifest import PackRefusedError

# Imported as shipped, before the tests' own key joins it while each test runs.
from modules.jobs.packs.signature import PACK_PUBLIC_KEYS_HEX as SHIPPED_KEYS

pytestmark = pytest.mark.unit

CONTRACTS = Path(__file__).resolve().parents[5] / "docs" / "contracts"
CONTRACT_6 = "06-job-pack-delivery.md"
SAMPLE_ZIP = "sample-jobs-1.0.0.zip"


@pytest.fixture
def sample() -> Path:
    """The sample's folder. Once contract 6 is here, a sample missing from it fails."""
    if not (CONTRACTS / CONTRACT_6).is_file():
        pytest.skip(
            f"contract 6 (docs/contracts/{CONTRACT_6}) is not in this repository yet, "
            "and its sample comes with it"
        )
    return CONTRACTS / "job-pack-sample"


def copied(sample: Path, tmp_path: Path) -> Path:
    """A copy of the sample's zip, so nothing is written beside the contract."""
    copy = tmp_path / SAMPLE_ZIP
    shutil.copyfile(sample / SAMPLE_ZIP, copy)
    return copy


def test_the_contract_sample_installs_with_its_key_trusted(
    sample: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trusted as the tests trust their own key: beside the shipped ones."""
    key = (sample / "public-key.hex").read_text(encoding="ascii").strip()
    monkeypatch.setattr(signature, "PACK_PUBLIC_KEYS_HEX", (key, *SHIPPED_KEYS))

    manifest = install_pack(copied(sample, tmp_path), tmp_path / "installed")

    assert (manifest.id, manifest.version) == ("sample-jobs", "1.0.0")
    assert [(job.key, job.runner, job.entitlement) for job in manifest.jobs] == [
        ("sample-questionnaire", "workbook-rows/1", "JOB_QUESTIONNAIRE")
    ]


def test_the_contract_sample_is_refused_with_the_shipped_keys_alone(
    sample: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test key signed it, which no release trusts."""
    monkeypatch.setattr(signature, "PACK_PUBLIC_KEYS_HEX", SHIPPED_KEYS)

    with pytest.raises(PackRefusedError) as refused:
        install_pack(copied(sample, tmp_path), tmp_path / "installed")

    assert refused.value.code == "PACK_BAD_SIGNATURE"
    assert installed_packs(tmp_path / "installed") == []
