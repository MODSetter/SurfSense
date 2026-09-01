"""First-sync and later mirror. Real store + dest git, no fakes of either."""

from __future__ import annotations

import pytest

from app.knowledge_store.engines.git import GitContentEngine
from app.knowledge_store.remote.paths import full_name_from_url, mount
from tests.integration.knowledge_store.remote.test_connect import (
    AUTHOR,
    PAT,
    gitlab_spec,
    store_for,
)

pytestmark = pytest.mark.integration


def _seed_docs(tmp_path, dest: GitContentEngine, writes: dict[str, bytes]) -> None:
    seed = GitContentEngine(tmp_path / "seed-docs", tmp_path / "seed-docs-wc")
    seed.record(writes=writes, removes=[], message="docs", author=AUTHOR)
    seed.push(
        url=str(dest._path),
        ref="refs/heads/main",
        username="oauth2",
        password=PAT,
    )


def _remote_head_bytes(dest: GitContentEngine, path: str) -> bytes:
    """Read a file at the remote's current main tip (proves what was pushed)."""
    from dulwich.repo import Repo

    repo = Repo(str(dest._path))
    try:
        sha = repo.refs[b"refs/heads/main"].decode()
    finally:
        repo.close()
    return dest.read_as_of(sha, path)


async def test_first_sync_from_remote_lands_under_the_mount(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    _seed_docs(
        tmp_path,
        dest,
        {
            "docs/intro.md": b"hello from gitlab",
            "docs/logo.png": b"PNG",
            "src/app.ts": b"not imported",
        },
    )
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))

    head = await store.head()
    assert head is not None
    prefix = mount(
        provider="gitlab",
        full_name=full_name_from_url(str(dest._path)),
        sourcepath="docs",
    )
    assert await store.read_as_of(head, f"{prefix}/intro.md") == b"hello from gitlab"
    paths = {p.path for p in await store.list_paths(head)}
    assert f"{prefix}/logo.png" not in paths
    assert not any(path.endswith("app.ts") for path in paths)


async def test_text_formats_sync_and_binaries_are_skipped(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    _seed_docs(
        tmp_path,
        dest,
        {
            "docs/guide.txt": b"plain text",
            "docs/spec.rst": b"restructured",
            "docs/report.pdf": b"%PDF-1.4 binary",
        },
    )
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))
    prefix = mount(
        provider="gitlab",
        full_name=full_name_from_url(str(dest._path)),
        sourcepath="docs",
    )
    # Pull: text documents land under the mount; the pdf stays a remote-only binary.
    head = await store.head()
    assert await store.read_as_of(head, f"{prefix}/guide.txt") == b"plain text"
    assert await store.read_as_of(head, f"{prefix}/spec.rst") == b"restructured"
    paths = {p.path for p in await store.list_paths(head)}
    assert f"{prefix}/report.pdf" not in paths

    # Push: a locally authored non-md text doc mirrors out; the pdf survives.
    async with store.transaction(message="add notes", author=AUTHOR) as tx:
        tx.write(f"{prefix}/notes.mdx", b"from us")
    await store.remotes.sync()

    from dulwich.repo import Repo

    repo = Repo(str(dest._path))
    try:
        sha = repo.refs[b"refs/heads/main"].decode()
    finally:
        repo.close()
    assert dest.read_as_of(sha, "docs/notes.mdx") == b"from us"
    assert dest.read_as_of(sha, "docs/report.pdf") == b"%PDF-1.4 binary"


async def test_both_sides_with_content_defers_to_the_user(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    _seed_docs(tmp_path, dest, {"docs/intro.md": b"theirs"})
    store = store_for(db_workspace, db_session)
    prefix = mount(
        provider="gitlab",
        full_name=full_name_from_url(str(dest._path)),
        sourcepath="docs",
    )
    async with store.transaction(message="local note", author=AUTHOR) as tx:
        tx.write(f"{prefix}/intro.md", b"ours")

    # Connect succeeds but mirrors nothing; the row asks the user to pick a side.
    status = await store.remotes.add(gitlab_spec(dest))
    assert status.last_error_code == "need_direction"
    assert (await store.remotes.list())[0].last_error_code == "need_direction"

    # Neither side was overwritten while awaiting a decision.
    head = await store.head()
    assert await store.read_as_of(head, f"{prefix}/intro.md") == b"ours"
    assert _remote_head_bytes(dest, "docs/intro.md") == b"theirs"

    # Choosing "keep local" pushes our copy and clears the attention flag.
    await store.remotes.resolve(direction="from_local")
    resolved = (await store.remotes.list())[0]
    assert resolved.last_error_code is None
    assert resolved.last_pushed_revision is not None
    assert _remote_head_bytes(dest, "docs/intro.md") == b"ours"


async def test_a_save_under_the_mount_is_pushed(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    _seed_docs(
        tmp_path,
        dest,
        {"docs/intro.md": b"hello from gitlab", "docs/logo.png": b"PNG"},
    )
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))
    prefix = mount(
        provider="gitlab",
        full_name=full_name_from_url(str(dest._path)),
        sourcepath="docs",
    )
    async with store.transaction(message="add guide", author=AUTHOR) as tx:
        tx.write(f"{prefix}/guide.md", b"from us")
    await store.remotes.sync()

    from dulwich.repo import Repo

    repo = Repo(str(dest._path))
    try:
        sha = repo.refs[b"refs/heads/main"].decode()
    finally:
        repo.close()
    assert dest.read_as_of(sha, "docs/guide.md") == b"from us"
    assert dest.read_as_of(sha, "docs/intro.md") == b"hello from gitlab"
    assert dest.read_as_of(sha, "docs/logo.png") == b"PNG"


async def test_a_save_outside_the_mount_is_not_pushed(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    _seed_docs(tmp_path, dest, {"docs/intro.md": b"hello from gitlab"})
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))
    async with store.transaction(message="private note", author=AUTHOR) as tx:
        tx.write("documents/notes/secret.md", b"stay here")
    await store.remotes.sync()

    from dulwich.repo import Repo

    repo = Repo(str(dest._path))
    try:
        sha = repo.refs[b"refs/heads/main"].decode()
    finally:
        repo.close()
    paths = {p.path for p in dest.list_paths(sha)}
    assert "documents/notes/secret.md" not in paths
    assert dest.read_as_of(sha, "docs/intro.md") == b"hello from gitlab"


def _dest_main(dest: GitContentEngine) -> str:
    from dulwich.repo import Repo

    repo = Repo(str(dest._path))
    try:
        return repo.refs[b"refs/heads/main"].decode()
    finally:
        repo.close()


async def test_conflict_stamps_and_writes_nothing(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    _seed_docs(tmp_path, dest, {"docs/intro.md": b"base"})
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))
    prefix = mount(
        provider="gitlab",
        full_name=full_name_from_url(str(dest._path)),
        sourcepath="docs",
    )
    async with store.transaction(message="local edit", author=AUTHOR) as tx:
        tx.write(f"{prefix}/intro.md", b"ours")

    from app.knowledge_store.remote.shadow import Shadow

    editor = Shadow.clone(str(dest._path), tmp_path / "editor", branch="main")
    editor.replace_text("docs", {"intro.md": b"theirs"})
    editor.commit(message="remote edit", author=AUTHOR)
    editor.push(url=str(dest._path), ref="refs/heads/main")

    await store.remotes.sync()

    head = await store.head()
    assert await store.read_as_of(head, f"{prefix}/intro.md") == b"ours"
    assert dest.read_as_of(_dest_main(dest), "docs/intro.md") == b"theirs"
    from sqlalchemy import select

    from app.knowledge_store.remote.persistence.models import WorkspaceGitRemotes

    row = await db_session.scalar(
        select(WorkspaceGitRemotes).where(
            WorkspaceGitRemotes.workspace_id == db_workspace.id
        )
    )
    assert row.last_error_code == "conflict"


async def test_resolve_from_remote_takes_theirs(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    _seed_docs(tmp_path, dest, {"docs/intro.md": b"base"})
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))
    prefix = mount(
        provider="gitlab",
        full_name=full_name_from_url(str(dest._path)),
        sourcepath="docs",
    )
    async with store.transaction(message="local edit", author=AUTHOR) as tx:
        tx.write(f"{prefix}/intro.md", b"ours")
    from app.knowledge_store.remote.shadow import Shadow

    editor = Shadow.clone(str(dest._path), tmp_path / "editor", branch="main")
    editor.replace_text("docs", {"intro.md": b"theirs"})
    editor.commit(message="remote edit", author=AUTHOR)
    editor.push(url=str(dest._path), ref="refs/heads/main")
    await store.remotes.sync()

    await store.remotes.resolve(direction="from_remote")

    head = await store.head()
    assert await store.read_as_of(head, f"{prefix}/intro.md") == b"theirs"
    from sqlalchemy import select

    from app.knowledge_store.remote.persistence.models import WorkspaceGitRemotes

    row = await db_session.scalar(
        select(WorkspaceGitRemotes).where(
            WorkspaceGitRemotes.workspace_id == db_workspace.id
        )
    )
    assert row.last_error_code is None


async def test_resolve_from_local_takes_ours(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    _seed_docs(tmp_path, dest, {"docs/intro.md": b"base"})
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))
    prefix = mount(
        provider="gitlab",
        full_name=full_name_from_url(str(dest._path)),
        sourcepath="docs",
    )
    async with store.transaction(message="local edit", author=AUTHOR) as tx:
        tx.write(f"{prefix}/intro.md", b"ours")
    from app.knowledge_store.remote.shadow import Shadow

    editor = Shadow.clone(str(dest._path), tmp_path / "editor", branch="main")
    editor.replace_text("docs", {"intro.md": b"theirs"})
    editor.commit(message="remote edit", author=AUTHOR)
    editor.push(url=str(dest._path), ref="refs/heads/main")
    await store.remotes.sync()

    await store.remotes.resolve(direction="from_local")

    head = await store.head()
    assert await store.read_as_of(head, f"{prefix}/intro.md") == b"ours"
    assert dest.read_as_of(_dest_main(dest), "docs/intro.md") == b"ours"
    statuses = await store.remotes.list()
    assert statuses[0].last_error_code is None


async def test_open_worktree_defers_sync(
    knowledge_root,
    tmp_path,
    db_session,
    db_workspace,
    dest,
    local_gitlab,
    delayed,
    workspace_flip,
    celery_session_on_test_connection,
):
    workspace_flip(True)
    _seed_docs(tmp_path, dest, {"docs/intro.md": b"base"})
    store = store_for(db_workspace, db_session)
    await store.remotes.add(gitlab_spec(dest))
    prefix = mount(
        provider="gitlab",
        full_name=full_name_from_url(str(dest._path)),
        sourcepath="docs",
    )
    await store.open_working_copy("thread-1")
    from app.knowledge_store.remote.shadow import Shadow

    editor = Shadow.clone(str(dest._path), tmp_path / "editor", branch="main")
    editor.replace_text("docs", {"intro.md": b"theirs"})
    editor.commit(message="remote edit", author=AUTHOR)
    editor.push(url=str(dest._path), ref="refs/heads/main")

    await store.remotes.sync()

    head = await store.head()
    assert await store.read_as_of(head, f"{prefix}/intro.md") == b"base"
    from sqlalchemy import select

    from app.knowledge_store.remote.persistence.models import WorkspaceGitRemotes

    row = await db_session.scalar(
        select(WorkspaceGitRemotes).where(
            WorkspaceGitRemotes.workspace_id == db_workspace.id
        )
    )
    assert row.last_error_code == "worktree_busy"
