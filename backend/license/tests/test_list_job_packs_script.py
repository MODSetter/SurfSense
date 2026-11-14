"""`python -m license.scripts.list_job_packs`: what the store would serve, and why the rest is refused."""

from __future__ import annotations

from pathlib import Path

import pytest

from license.scripts import list_job_packs as script
from license.settings import config
from license.tests.github_fake import FakeGitHub
from license.tests.job_pack_samples import pack_zip, write_pack

pytestmark = pytest.mark.unit


@pytest.fixture
def folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """JOB_PACKS_DIR, and no GitHub."""
    monkeypatch.setattr(config, "JOB_PACKS_DIR", str(tmp_path))
    monkeypatch.setattr(config, "JOB_PACKS_GITHUB_REPO", "")
    monkeypatch.setattr(config, "JOB_PACKS_GITHUB_TOKEN", "")
    return tmp_path


async def test_each_served_job_and_each_refused_asset_is_named(
    folder: Path, trusted_pack_key, capsys: pytest.CaptureFixture
) -> None:
    write_pack(folder, version="1.0.0")
    write_pack(folder, version="1.1.0", keys=())

    assert await script.main([]) == 0
    out = capsys.readouterr().out

    assert (
        "sample-jobs 1.0.0: sample-questionnaire (workbook-rows/1) for JOB_QUESTIONNAIRE"
        in out
    )
    assert "sample-jobs-1.1.0.zip: refused, PACK_NOT_SIGNED: " in out


async def test_a_store_that_cannot_be_read_exits_1(
    folder: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(config, "JOB_PACKS_DIR", str(folder / "missing"))

    assert await script.main([]) == 1
    assert "cannot be read" in capsys.readouterr().err


async def test_no_store_exits_1(
    folder: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(config, "JOB_PACKS_DIR", "")

    assert await script.main([]) == 1
    assert "JOB_PACKS_DIR" in capsys.readouterr().err


async def test_nothing_passing_exits_1(
    folder: Path, trusted_pack_key, capsys: pytest.CaptureFixture
) -> None:
    write_pack(folder, access="free")

    assert await script.main([]) == 1
    captured = capsys.readouterr()
    assert "sample-jobs-1.0.0.zip: refused, PACK_NOT_PAID: " in captured.out
    assert "No job pack passes" in captured.err


@pytest.mark.parametrize("status", [None, 401])
async def test_the_token_is_never_printed(
    github: FakeGitHub,
    trusted_pack_key,
    capsys: pytest.CaptureFixture,
    status: int | None,
) -> None:
    github.publish("sample-jobs-v1.0.0", "sample-jobs-1.0.0.zip", pack_zip())
    github.status = status

    code = await script.main([])

    captured = capsys.readouterr()
    assert code == (0 if status is None else 1)
    assert github.token not in captured.out + captured.err
