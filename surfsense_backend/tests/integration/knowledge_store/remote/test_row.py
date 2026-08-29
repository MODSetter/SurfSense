"""A GitLab PAT is ciphertext in Postgres and absent from status."""

from __future__ import annotations

import pytest

from sqlalchemy import select

from app.config import config
from app.knowledge_store.remote.persistence.models import WorkspaceGitRemotes
from app.knowledge_store.remote.persistence.repository import WorkspaceRemoteRepository
from app.knowledge_store.remote.schemas import GitlabSpec
from app.utils.oauth_security import TokenEncryption

pytestmark = pytest.mark.integration

PAT = "glpat-super-secret-token"


async def test_save_encrypts_the_pat_and_omits_it_from_status(db_session, db_workspace):
    rows = WorkspaceRemoteRepository(db_session)
    status = await rows.save(
        db_workspace.id,
        GitlabSpec(
            provider="gitlab",
            url="https://gitlab.com/o/r.git",
            token=PAT,
        ),
    )

    assert not hasattr(status, "token")
    listed = await rows.list_statuses(db_workspace.id)
    assert listed == [status]
    assert listed[0].url == "https://gitlab.com/o/r.git"
    assert listed[0].provider == "gitlab"

    stored = await db_session.scalar(
        select(WorkspaceGitRemotes).where(
            WorkspaceGitRemotes.workspace_id == db_workspace.id
        )
    )
    assert stored is not None
    assert stored.token != PAT
    cipher = TokenEncryption(config.SECRET_KEY)
    assert cipher.is_encrypted(stored.token)
    assert cipher.decrypt_token(stored.token) == PAT

    spec = await rows.get_spec(db_workspace.id)
    assert spec is not None
    assert spec.token == PAT
