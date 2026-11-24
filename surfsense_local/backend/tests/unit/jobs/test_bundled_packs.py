"""The job packs the app ships (ADR 0092): signed with SurfSense's pack key, Apache-2.0, and
installed at start unless that version or a newer one is installed already."""

import logging
from pathlib import Path

import pytest

from modules.jobs.packs import signature
from modules.jobs.packs.bundled_packs import bundled_packs, install_bundled_packs
from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import installed_packs
from modules.jobs.packs.integrity import check_files
from modules.jobs.packs.manifest import parse_manifest, read_raw_manifest
from tests.job_pack_samples import (
    PACK_ID,
    TEST_PACK_PUBLIC_KEY_HEX,
    write_questionnaire_pack,
)

pytestmark = pytest.mark.unit

SHIPPED = {
    "surfsense-contract-redline": "JOB_CONTRACT_REDLINE",
    "surfsense-security-questionnaire": "JOB_QUESTIONNAIRE",
}


class NoRunsInFlight:
    """The sessions `install_bundled_packs` opens, on a database with no run under way."""

    def __call__(self) -> "NoRunsInFlight":
        return self

    def __enter__(self) -> "NoRunsInFlight":
        return self

    def __exit__(self, *_: object) -> None:
        return None


@pytest.fixture
def no_runs(monkeypatch: pytest.MonkeyPatch) -> NoRunsInFlight:
    """Sessions on which no pack is in use."""
    monkeypatch.setattr(
        "modules.jobs.packs.bundled_packs.pack_in_use", lambda _session, _id: False
    )
    return NoRunsInFlight()


@pytest.fixture
def installed_into(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The installed packs' folder, in the test's own space."""
    root = tmp_path / "installed"
    monkeypatch.setattr("modules.jobs.packs.dev_packs.packs_dir", lambda: root)
    monkeypatch.setattr(
        "modules.jobs.packs.bundled_packs.installed_packs",
        lambda: installed_packs(root),
    )
    return root


def test_the_shipped_packs_pass_the_checks_of_a_shipped_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checked against the compiled keys alone, as a release checks them."""
    monkeypatch.setattr(
        signature,
        "PACK_PUBLIC_KEYS_HEX",
        tuple(
            k for k in signature.PACK_PUBLIC_KEYS_HEX if k != TEST_PACK_PUBLIC_KEY_HEX
        ),
    )
    found = {}
    for folder in bundled_packs():
        raw = read_raw_manifest(folder)
        signature.check_signature(folder, raw)
        manifest = parse_manifest(raw)
        check_files(folder, manifest)
        found[manifest.id] = [job.entitlement for job in manifest.jobs]

    assert found == {pack: [code] for pack, code in SHIPPED.items()}


def test_every_shipped_pack_is_apache_2_0() -> None:
    """The proprietary pack licence is gone with the company's licensing."""
    for folder in bundled_packs():
        manifest = parse_manifest(read_raw_manifest(folder))
        text = (folder / manifest.license_file).read_text(encoding="utf-8")
        assert "Apache License, Version 2.0" in text, folder.name
        assert "proprietary" not in text.lower(), folder.name


def test_they_install_at_start_and_a_second_start_changes_nothing(
    installed_into: Path, no_runs: NoRunsInFlight, caplog: pytest.LogCaptureFixture
) -> None:
    """Once in place, a start neither copies nor logs anything."""
    caplog.set_level(logging.INFO, "modules.jobs.packs.dev_packs")
    install_bundled_packs(no_runs)
    first = {p.manifest.id: p.folder for p in installed_packs(installed_into)}
    caplog.clear()

    install_bundled_packs(no_runs)

    assert set(first) == set(SHIPPED)
    assert {p.manifest.id: p.folder for p in installed_packs(installed_into)} == first
    assert caplog.records == []


def test_a_newer_installed_version_is_kept(
    installed_into: Path,
    no_runs: NoRunsInFlight,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An imported newer pack is never replaced by the older one the app ships."""
    shipped = tmp_path / "shipped"
    write_questionnaire_pack(shipped / "test", version="1.0.0")
    install_pack(
        write_questionnaire_pack(tmp_path / "newer", version="2.0.0"), installed_into
    )
    monkeypatch.setattr("modules.jobs.packs.bundled_packs.BUNDLED_PACKS", shipped)

    install_bundled_packs(no_runs)

    assert [
        (p.manifest.id, p.manifest.version) for p in installed_packs(installed_into)
    ] == [(PACK_ID, "2.0.0")]


def test_an_older_installed_version_is_replaced(
    installed_into: Path,
    no_runs: NoRunsInFlight,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A licence-era download of a pack gives way to the Apache-2.0 version the app ships."""
    shipped = tmp_path / "shipped"
    write_questionnaire_pack(shipped / "test", version="2.0.0")
    install_pack(
        write_questionnaire_pack(tmp_path / "older", version="1.0.0"), installed_into
    )
    monkeypatch.setattr("modules.jobs.packs.bundled_packs.BUNDLED_PACKS", shipped)

    install_bundled_packs(no_runs)

    assert [
        (p.manifest.id, p.manifest.version) for p in installed_packs(installed_into)
    ] == [(PACK_ID, "2.0.0")]
