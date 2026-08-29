"""Connect a local dest as a GitLab remote, then push HEAD through the worker."""

from __future__ import annotations

import pytest

import app.tasks.celery_tasks.knowledge_store.push_task as push_task
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.engines.git import GitContentEngine
from app.knowledge_store.identities import user_identity
from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.schemas import GitlabSpec

pytestmark = pytest.mark.integration

PAT = "glpat-integration-secret"
AUTHOR = user_identity("1")


def gitlab_spec(dest: GitContentEngine, *, branch: str = "main") -> GitlabSpec:
    return GitlabSpec(
        provider="gitlab",
        url=str(dest._path),
        token=PAT,
        branch=branch,
    )


def store_for(workspace, session) -> KnowledgeStore:
    return KnowledgeStore.for_workspace(workspace.id).with_session(session)


async def _record(store, path: str = "documents/a.md", content: bytes = b"hello"):
    async with store.transaction(message="seed", author=AUTHOR) as tx:
        tx.write(path, content)
    return tx.revision


def _seed_main(tmp_path, dest: GitContentEngine) -> None:
    seed = GitContentEngine(tmp_path / "seed", tmp_path / "seed-wc")
    seed.record(
        writes={"documents/x.md": b"occupied"},
        removes=[],
        message="occupy main",
        author=AUTHOR,
    )
    seed.push(
        url=str(dest._path),
        ref="refs/heads/main",
        username="oauth2",
        password=PAT,
    )


async def test_unflipped_workspace_cannot_add(
    knowledge_root,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
):
    workspace_flip(False)
    store = store_for(db_workspace, db_session)
    with pytest.raises(RemoteError) as exc:
        await store.remotes.add(gitlab_spec(dest))
    assert exc.value.code == "not_git_native"
    assert delayed == []
    assert await store.remotes.list() == []


async def test_second_remote_is_refused(
    knowledge_root,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))
    with pytest.raises(RemoteError) as exc:
        await store.remotes.add(gitlab_spec(dest))
    assert exc.value.code == "already_exists"
    assert delayed == [db_workspace.id]


async def test_non_empty_branch_is_refused(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
):
    workspace_flip(True)
    _seed_main(tmp_path, dest)
    store = store_for(db_workspace, db_session)
    with pytest.raises(RemoteError) as exc:
        await store.remotes.add(gitlab_spec(dest))
    assert exc.value.code == "not_empty"
    assert delayed == []
    assert await store.remotes.list() == []


async def test_add_then_push_copies_head_and_keeps_the_pat_off_status(
    knowledge_root,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    store = store_for(db_workspace, db_session)
    rev = await _record(store)

    status = await store.remotes.add(gitlab_spec(dest))
    listed = await store.remotes.list()
    assert listed == [status]
    assert status.provider == "gitlab"
    assert status.url == str(dest._path)
    assert status.last_pushed_revision is None
    assert not hasattr(status, "token")
    assert delayed == [db_workspace.id]

    creds = await store.remotes.credentials()
    assert creds.username == "oauth2"
    assert creds.password == PAT

    sha = await push_task._push(db_workspace.id)
    assert sha == rev
    assert dest.read_as_of(rev, "documents/a.md") == b"hello"

    db_session.expire_all()
    after = (await store.remotes.list())[0]
    assert after.last_pushed_revision == rev
    assert after.last_push_error is None


async def test_worker_noops_without_a_remote(
    knowledge_root,
    db_session,
    db_workspace,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    store = store_for(db_workspace, db_session)
    await _record(store)
    assert await push_task._push(db_workspace.id) is None


async def test_worker_noops_when_already_pushed(
    knowledge_root,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    store = store_for(db_workspace, db_session)
    await _record(store)
    await store.remotes.add(gitlab_spec(dest))
    assert await push_task._push(db_workspace.id) is not None
    assert await push_task._push(db_workspace.id) is None


async def test_remove_clears_the_row(
    knowledge_root,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))
    await store.remotes.remove()
    assert await store.remotes.list() == []
    assert await push_task._push(db_workspace.id) is None


async def test_sweep_enqueues_when_stamp_trails_head(
    knowledge_root,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    db_workspace.knowledge_store_enabled = True
    await db_session.flush()
    store = store_for(db_workspace, db_session)
    await _record(store)
    await store.remotes.add(gitlab_spec(dest))
    delayed.clear()

    assert await push_task._sweep() == 1
    assert delayed == [db_workspace.id]


async def test_sweep_skips_when_stamp_matches_head(
    knowledge_root,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    db_workspace.knowledge_store_enabled = True
    await db_session.flush()
    store = store_for(db_workspace, db_session)
    await _record(store)
    await store.remotes.add(gitlab_spec(dest))
    await push_task._push(db_workspace.id)
    delayed.clear()

    assert await push_task._sweep() == 0
    assert delayed == []
