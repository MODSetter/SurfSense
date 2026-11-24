"""A dev build installs the packs its environment names when the API starts, and a bad one never stops it."""

import os

import pytest

from modules.jobs.packs.dev_packs import DEV_PACKS, install_dev_packs
from modules.jobs.packs.installed import installed_packs, packs_dir
from tests.job_pack_samples import write_questionnaire_pack

pytestmark = pytest.mark.unit


def test_the_named_packs_install_and_a_missing_one_is_only_logged(
    tmp_path, monkeypatch, caplog
):
    """A folder named in the environment is installed; a path that is no pack is logged and skipped."""
    monkeypatch.setattr(
        "modules.jobs.packs.dev_packs.packs_dir", lambda: tmp_path / "installed"
    )
    pack = write_questionnaire_pack(tmp_path / "pack")
    monkeypatch.setenv(
        DEV_PACKS, os.pathsep.join([str(tmp_path / "missing"), str(pack)])
    )

    install_dev_packs()

    assert [p.manifest.id for p in installed_packs(tmp_path / "installed")] == [
        "test-jobs"
    ]
    assert "not installed" in caplog.text
    assert packs_dir() != tmp_path / "installed"
