"""With licensing off (ADR 0092) a paid job runs with no licence, or with one that ended."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from modules.jobs.packs.access import DEV_SWITCH
from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import packs_dir
from modules.license.licensing import OVERRIDE
from modules.workspaces.models import Workspace
from tests.integration.artifacts.job_runs.started_runs import start_run
from tests.job_pack_samples import write_questionnaire_pack
from tests.license_samples import business_license, trust_sample_licenses

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def licensing_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """As a release runs, with the paid test pack installed and no developer switch."""
    monkeypatch.delenv(OVERRIDE, raising=False)
    monkeypatch.delenv(DEV_SWITCH, raising=False)
    trust_sample_licenses(monkeypatch)
    install_pack(write_questionnaire_pack(tmp_path / "pack-source"), packs_dir())


async def test_a_paid_job_starts_with_no_license(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """Nothing imported, nor ever was."""
    assert await start_run(client, session, workspace.id) > 0


async def test_a_paid_job_starts_on_a_license_that_ended(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """The licence is read, but no longer decides."""
    ended = business_license(expiry="2026-09-01T00:00:00.000Z")
    imported = await client.put("/license", json={"certificate": ended})
    assert imported.status_code == 200, imported.text
    assert imported.json()["state"] == "license_expired"

    assert await start_run(client, session, workspace.id) > 0
