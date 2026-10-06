"""Each agent thread's folder holds the sources its turns may use, mirrored in the user's folders."""

import asyncio
import os
import sqlite3
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.main import create_app
from modules.agent.thread_folder import sync as sync_module
from modules.agent.thread_folder import text_cache
from modules.agent.thread_folder.sync import ThreadGoneError, sync_thread_folder
from modules.chat.models import ChatThread
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.folders.models import Folder
from modules.folders.names import name_key
from modules.source_roots.managed_root import ensure_managed_root
from modules.source_scope.resolve import resolve_scope
from modules.source_scope.schemas import SourceScope
from modules.workspaces.models import Workspace
from shared.config import get_agent_settings, get_storage_settings
from shared.db import create_session_factory
from tests.integration.agent.conftest import MAX_PATH

pytestmark = pytest.mark.integration


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on this test's migrated database."""
    with create_session_factory(engine)() as session:
        yield session


def workspace(session: Session) -> int:
    """A new workspace's id."""
    row = Workspace(name="Research")
    session.add(row)
    session.commit()
    return row.id


def agent_thread(session: Session, workspace_id: int) -> ChatThread:
    """A thread the agent answers, as opening one leaves it."""
    thread = ChatThread(
        workspace_id=workspace_id, title="New chat", opencode_session_id="ses_test"
    )
    session.add(thread)
    session.commit()
    return thread


def folder_in_library(session: Session, workspace_id: int, name: str) -> int:
    """A folder at the Library's top, as the sources panel makes one."""
    library = ensure_managed_root(session, workspace_id)
    folder = Folder(
        workspace_id=workspace_id,
        root_id=library.root_id,
        parent_id=library.id,
        name=name,
        name_key=name_key(name),
    )
    session.add(folder)
    session.commit()
    return folder.id


def source(
    session: Session,
    workspace_id: int,
    title: str,
    content: str,
    folder_id: int | None = None,
) -> Document:
    """A ready note, filed where given."""
    document = Document(
        workspace_id=workspace_id,
        title=title,
        document_type=DocumentType.NOTE,
        status=DocumentStatus.READY,
        content=content,
        folder_id=folder_id,
    )
    session.add(document)
    session.commit()
    return document


def texts(folder: Path) -> dict[str, str]:
    """Each file under `sources/`, by its path there, with its text."""
    sources = folder / "sources"
    return {
        path.relative_to(sources).as_posix(): path.read_text(encoding="utf-8")
        for path in sources.rglob("*")
        if path.is_file()
    }


def test_two_threads_each_hold_only_their_own_sources_in_the_users_folders(
    session: Session,
) -> None:
    """A thread's folder is the agent's whole view: another thread's ticks never show in it."""
    workspace_id = workspace(session)
    research = folder_in_library(session, workspace_id, "Research")
    plan = source(session, workspace_id, "Plan", "Ship on Friday.", research)
    memo = source(session, workspace_id, "Memo", "Ship on Monday.", research)
    first, second = (
        agent_thread(session, workspace_id),
        agent_thread(session, workspace_id),
    )

    one = sync_thread_folder(session, first, [plan.id])
    other = sync_thread_folder(session, second, [memo.id])

    assert one != other
    assert texts(one) == {f"Library/Research/Plan [{plan.id}].md": "Ship on Friday."}
    assert texts(other) == {f"Library/Research/Memo [{memo.id}].md": "Ship on Monday."}


def test_an_untick_takes_the_text_figures_and_pages_from_that_thread_only(
    session: Session,
) -> None:
    """What one thread was shown of a source leaves with its tick, there alone."""
    workspace_id = workspace(session)
    kept = source(session, workspace_id, "Plan", "Q3")
    gone = source(session, workspace_id, "Old", "Q2")
    first, second = (
        agent_thread(session, workspace_id),
        agent_thread(session, workspace_id),
    )
    for thread in (first, second):
        folder = sync_thread_folder(session, thread, [kept.id, gone.id])
        for document in (kept, gone):
            (folder / "sources" / "figures").mkdir(exist_ok=True)
            (folder / "sources" / "figures" / f"{document.id}-1.png").write_bytes(b"f")
            (folder / "sources" / "pages").mkdir(exist_ok=True)
            (folder / "sources" / "pages" / f"{document.id}-p1.png").write_bytes(b"p")

    one = sync_thread_folder(session, first, [kept.id])
    other = sync_thread_folder(session, second, [kept.id, gone.id])

    assert set(texts(one)) == {
        f"Plan [{kept.id}].md",
        f"figures/{kept.id}-1.png",
        f"pages/{kept.id}-p1.png",
    }
    assert len(texts(other)) == 6


def test_two_threads_share_one_file_for_one_text(session: Session) -> None:
    """The virus scanner reads a written file once; a link is that file again."""
    workspace_id = workspace(session)
    plan = source(session, workspace_id, "Plan", "Ship on Friday.")
    first, second = (
        agent_thread(session, workspace_id),
        agent_thread(session, workspace_id),
    )

    one = sync_thread_folder(session, first, [plan.id])
    other = sync_thread_folder(session, second, [plan.id])

    name = f"sources/Plan [{plan.id}].md"
    assert os.path.samefile(one / name, other / name)


def test_a_disk_that_cannot_link_gets_copies_of_equal_text(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FAT and exFAT have no hard links."""

    def no_links(*_args: object) -> None:
        raise OSError("hard links are not supported")

    monkeypatch.setattr(text_cache.os, "link", no_links)
    workspace_id = workspace(session)
    plan = source(session, workspace_id, "Plan", "Ship on Friday.")
    first, second = (
        agent_thread(session, workspace_id),
        agent_thread(session, workspace_id),
    )

    one = sync_thread_folder(session, first, [plan.id])
    other = sync_thread_folder(session, second, [plan.id])

    name = f"sources/Plan [{plan.id}].md"
    assert not os.path.samefile(one / name, other / name)
    assert texts(one) == texts(other) == {f"Plan [{plan.id}].md": "Ship on Friday."}


def test_two_changes_in_one_second_are_both_seen(session: Session) -> None:
    """The text decides the version, never a timestamp with one-second steps."""
    workspace_id = workspace(session)
    note = source(session, workspace_id, "Plan", "Version A.")
    thread = agent_thread(session, workspace_id)
    seen = []
    for version in ("Version B.", "Version C."):
        note.content = version
        session.commit()
        seen.append(texts(sync_thread_folder(session, thread, [note.id])))

    assert [view[f"Plan [{note.id}].md"] for view in seen] == [
        "Version B.",
        "Version C.",
    ]
    cached = list(get_storage_settings().agent_text_dir(workspace_id).iterdir())
    assert [path.read_text(encoding="utf-8") for path in cached] == ["Version C."]


def test_a_cache_file_no_thread_links_is_swept_and_a_linked_one_stays(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deleted sources and old versions leave the cache; a text a thread still links stays."""
    workspace_id = workspace(session)
    plan = source(session, workspace_id, "Plan", "Ship on Friday.")
    thread = agent_thread(session, workspace_id)
    sync_thread_folder(session, thread, [plan.id])
    cache = get_storage_settings().agent_text_dir(workspace_id)
    (linked,) = cache.iterdir()
    orphan = cache / "999-0123456789abcdef.md"
    orphan.write_text("A deleted source.", encoding="utf-8")
    long_ago = time.time() - 3600
    for path in (linked, orphan):
        os.utime(path, (long_ago, long_ago))
    monkeypatch.setattr(sync_module, "SWEEP_SECONDS", 0)

    sync_thread_folder(session, thread, [plan.id])

    assert [path.name for path in cache.iterdir()] == [linked.name]


def test_two_syncs_of_one_thread_at_once_leave_one_whole_view(engine: Engine) -> None:
    """Two turns sent at once never leave a mix of both scopes."""
    factory = create_session_factory(engine)
    with factory() as session:
        workspace_id = workspace(session)
        a = [source(session, workspace_id, f"A{n}", f"a{n}").id for n in range(30)]
        b = [source(session, workspace_id, f"B{n}", f"b{n}").id for n in range(30)]
        thread = agent_thread(session, workspace_id)

    def sync(ids: list[int]) -> Path:
        with factory() as own:
            return sync_thread_folder(own, own.get(ChatThread, thread.id), ids)

    with ThreadPoolExecutor(2) as pool:
        folders = list(pool.map(sync, [a, b]))

    names = set(texts(folders[0]))
    assert names in (
        {f"A{n} [{i}].md" for n, i in enumerate(a)},
        {f"B{n} [{i}].md" for n, i in enumerate(b)},
    )


def test_a_view_that_is_not_the_cached_text_is_replaced(session: Session) -> None:
    """A file left from another run is replaced by the cached text itself."""
    workspace_id = workspace(session)
    plan = source(session, workspace_id, "Plan", "Ship on Friday.")
    thread = agent_thread(session, workspace_id)
    folder = sync_thread_folder(session, thread, [plan.id])
    view = folder / "sources" / f"Plan [{plan.id}].md"
    view.unlink()
    view.write_text("Stale.", encoding="utf-8")

    sync_thread_folder(session, thread, [plan.id])

    assert view.read_text(encoding="utf-8") == "Ship on Friday."


def test_the_folder_of_a_thread_that_is_gone_is_removed(session: Session) -> None:
    """A folder a failed delete left behind is swept on the first sync."""
    workspace_id = workspace(session)
    thread = agent_thread(session, workspace_id)
    storage = get_storage_settings()
    orphan = storage.thread_working_dir(workspace_id, thread.id + 100) / "outputs"
    orphan.mkdir(parents=True)

    sync_thread_folder(session, thread, [])

    assert not orphan.parent.exists()
    assert storage.thread_working_dir(workspace_id, thread.id).is_dir()


def test_the_first_sync_retires_the_shared_folder_and_keeps_its_outputs(
    session: Session,
) -> None:
    """Every thread once worked in agent/; what the agent wrote there stays with the workspace."""
    workspace_id = workspace(session)
    agent = get_storage_settings().agent_working_dir(workspace_id)
    (agent / "sources").mkdir(parents=True)
    (agent / "sources" / "Plan [1].md").write_text("Old.", encoding="utf-8")
    (agent / "outputs" / "previews" / "3-v1").mkdir(parents=True)
    (agent / "outputs" / "notes.md").write_text("Mine.", encoding="utf-8")

    sync_thread_folder(session, agent_thread(session, workspace_id), [])

    assert not (agent / "sources").exists()
    assert not (agent / "outputs" / "previews").exists()
    assert (agent / "outputs" / "notes.md").read_text(encoding="utf-8") == "Mine."


def test_an_output_named_like_an_instruction_file_is_renamed(session: Session) -> None:
    """opencode would read it as instructions; the edit rule misses mixed case off Windows."""
    workspace_id = workspace(session)
    thread = agent_thread(session, workspace_id)
    folder = sync_thread_folder(session, thread, [])
    (folder / "outputs" / "Agents.md").write_text("Obey.", encoding="utf-8")
    (folder / "outputs" / "drafts").mkdir()
    (folder / "outputs" / "drafts" / "context.md").write_text("Obey.", encoding="utf-8")

    sync_thread_folder(session, thread, [])

    assert sorted(
        path.relative_to(folder / "outputs").as_posix()
        for path in (folder / "outputs").rglob("*")
        if path.is_file()
    ) == ["Agents.md_", "drafts/context.md_"]


def test_anything_planted_among_the_sources_leaves(session: Session) -> None:
    """The agent greps `sources/`; only the mirror and SurfSense's images may outlive a sync."""
    workspace_id = workspace(session)
    plan = source(session, workspace_id, "Plan", "Draft.")
    thread = agent_thread(session, workspace_id)
    folder = sync_thread_folder(session, thread, [plan.id])
    planted = folder / "sources" / "Library" / "outputs"
    planted.mkdir(parents=True)
    (planted / "Fake [99].md").write_text("A fake source.", encoding="utf-8")
    (folder / "sources" / "figures" / "agent").mkdir(parents=True)
    (folder / "sources" / "pages").mkdir()
    (folder / "sources" / "pages" / "notes.txt").write_text("x", encoding="utf-8")

    sync_thread_folder(session, thread, [plan.id])

    assert texts(folder) == {f"Plan [{plan.id}].md": "Draft."}
    assert not (folder / "sources" / "Library").exists()


def test_the_agents_outputs_survive_a_sync(session: Session) -> None:
    """The output folder is the agent's own; syncing sources never touches it."""
    workspace_id = workspace(session)
    thread = agent_thread(session, workspace_id)
    folder = sync_thread_folder(session, thread, [])
    (folder / "outputs" / "summary.md").write_text("Done.", encoding="utf-8")

    sync_thread_folder(session, thread, [])

    assert (folder / "outputs" / "summary.md").read_text(encoding="utf-8") == "Done."


def test_another_writer_is_never_kept_waiting_while_sources_are_laid_out(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Notes are saved while a big scope syncs: no file is written inside a transaction."""
    factory = create_session_factory(engine)
    with factory() as session:
        workspace_id = workspace(session)
        session.add_all(
            Document(
                workspace_id=workspace_id,
                title=f"n{n}",
                document_type=DocumentType.NOTE,
                status=DocumentStatus.READY,
                content=f"note {n}",
            )
            for n in range(2000)
        )
        session.commit()
        ids = list(
            session.scalars(
                Document.__table__.select()
                .with_only_columns(Document.id)
                .where(Document.workspace_id == workspace_id)
            )
        )
        thread = agent_thread(session, workspace_id)
    writes: list[bool] = []
    link = sync_module.link_view

    def link_while_another_writes(*args: object) -> None:
        if len(writes) < 3:
            other = sqlite3.connect(
                get_storage_settings().database_path, timeout=0.1, isolation_level=None
            )
            try:
                other.execute("BEGIN IMMEDIATE")
                other.execute("ROLLBACK")
                writes.append(True)
            except sqlite3.OperationalError:
                writes.append(False)
            finally:
                other.close()
        link(*args)

    monkeypatch.setattr(sync_module, "link_view", link_while_another_writes)
    with factory() as session:
        folder = sync_thread_folder(session, session.get(ChatThread, thread.id), ids)

    assert writes == [True, True, True]
    assert len(texts(folder)) == 2000


SOURCES_MEASURED = 3000
TEXT_BYTES = 40_000


def test_sync_time_at_a_few_thousand_sources(engine: Engine, capsys) -> None:
    """A measurement: the first sync writes every text, a steady one only checks them."""
    factory = create_session_factory(engine)
    with factory() as session:
        workspace_id = workspace(session)
        research = folder_in_library(session, workspace_id, "Research")
        body = "x" * (TEXT_BYTES - 10)
        session.add_all(
            Document(
                workspace_id=workspace_id,
                title=f"Report {n}",
                document_type=DocumentType.NOTE,
                status=DocumentStatus.READY,
                content=f"{n:09d} {body}",
                folder_id=research,
            )
            for n in range(SOURCES_MEASURED)
        )
        session.commit()
        ids = list(
            session.scalars(
                Document.__table__.select()
                .with_only_columns(Document.id)
                .where(Document.workspace_id == workspace_id)
            )
        )
        first, second = (
            agent_thread(session, workspace_id),
            agent_thread(session, workspace_id),
        )

    timings = {}
    with factory() as session:
        for label, thread in (
            ("first", first),
            ("steady", first),
            ("second thread", second),
        ):
            began = time.perf_counter()
            sync_thread_folder(session, session.get(ChatThread, thread.id), ids)
            timings[label] = time.perf_counter() - began

    with capsys.disabled():
        print(  # noqa: T201
            f"\nsync of {SOURCES_MEASURED} sources of {TEXT_BYTES // 1000} KB: "
            + ", ".join(
                f"{label} {seconds:.2f} s" for label, seconds in timings.items()
            )
        )
    # Loose bounds, so only a regression of an order of magnitude fails.
    assert timings["steady"] < 30
    assert timings["second thread"] < 60


def test_a_title_cannot_reach_outside_the_folder(session: Session) -> None:
    """A title is user text; only a validated name reaches the disk."""
    workspace_id = workspace(session)
    note = source(session, workspace_id, "../../outside", "Text.")
    thread = agent_thread(session, workspace_id)

    folder = sync_thread_folder(session, thread, [note.id])

    (written,) = (folder / "sources").iterdir()
    assert written.parent == folder / "sources"
    assert written.name.endswith(f"[{note.id}].md")


def test_a_studio_artifact_filed_in_a_ticked_folder_is_there_to_read(
    session: Session,
) -> None:
    """The turn counts it among its sources, so the agent must be able to open it."""
    workspace_id = workspace(session)
    research = folder_in_library(session, workspace_id, "Research")
    quiz = Document(
        workspace_id=workspace_id,
        title="Quiz",
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.READY,
        content="Q1. When do we ship?",
        folder_id=research,
    )
    session.add(quiz)
    session.commit()
    resolved = resolve_scope(session, workspace_id, SourceScope(folder_ids=[research]))

    folder = sync_thread_folder(
        session, agent_thread(session, workspace_id), resolved.ids
    )

    assert resolved.counts.ready == 1
    assert texts(folder) == {
        f"Library/Research/Quiz [{quiz.id}].md": "Q1. When do we ship?"
    }


def test_a_source_in_a_folder_as_deep_as_fits_is_written_where_long_paths_are_off(
    session: Session, long_paths_off: list[str]
) -> None:
    """The layout keeps every file within MAX_PATH; so must the files a sync writes on the way."""
    workspace_id = workspace(session)
    thread = agent_thread(session, workspace_id)
    sources = get_storage_settings().thread_working_dir(workspace_id, thread.id)
    # A folder as deep as a file may still go in: 28 characters are left for it.
    deep = 230 - len(str(sources / "sources" / "Library")) - 1
    research = folder_in_library(session, workspace_id, "R" * deep)
    note = source(session, workspace_id, "Long " * 20, "Text.", research)

    folder = sync_thread_folder(session, thread, [note.id])

    ((name, text),) = texts(folder).items()
    assert len(str(folder / "sources" / name)) == MAX_PATH
    assert text == "Text."
    assert long_paths_off == []


def test_a_source_under_a_long_data_folder_is_written_where_long_paths_are_off(
    session: Session, long_paths_off: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Its cached text goes beside the shorter `agent/text/`, which must fit too."""
    storage = get_storage_settings()
    workspace_id = workspace(session)
    thread = agent_thread(session, workspace_id)
    padding = 235 - len(
        str(storage.thread_working_dir(workspace_id, thread.id) / "sources")
    )
    monkeypatch.setattr(storage, "data_dir", storage.data_dir / ("d" * padding))
    note = source(session, workspace_id, "Long " * 20, "Text.")

    folder = sync_thread_folder(session, thread, [note.id])

    ((name, text),) = texts(folder).items()
    # Cut to fit, less the space it would have ended on.
    assert len(str(folder / "sources" / name)) == MAX_PATH - 1
    assert text == "Text."
    assert long_paths_off == []


async def test_a_thread_deleted_while_its_folder_syncs_leaves_no_folder(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A turn sent from one tab syncs while another tab deletes the thread."""
    monkeypatch.setattr(get_agent_settings(), "opencode_url", None)
    factory = create_session_factory(engine)
    with factory() as session:
        workspace_id = workspace(session)
        plan = source(session, workspace_id, "Plan", "Ship on Friday.")
        thread_id = agent_thread(session, workspace_id).id
    reading, deleted = threading.Event(), threading.Event()
    texts_of = sync_module._texts

    def texts_once_deleted(*args: object) -> list[tuple[int, str]]:
        reading.set()
        deleted.wait(timeout=10)
        return texts_of(*args)

    monkeypatch.setattr(sync_module, "_texts", texts_once_deleted)

    def turn_sync() -> None:
        with factory() as own:
            sync_thread_folder(own, own.get(ChatThread, thread_id), [plan.id])

    app = create_app()
    app.state.session_factory = factory
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        syncing = asyncio.create_task(asyncio.to_thread(turn_sync))
        await asyncio.to_thread(reading.wait, 10)
        deleting = asyncio.create_task(client.delete(f"/chat/threads/{thread_id}"))
        await asyncio.sleep(0.5)
        deleted.set()
        reply, _ = await asyncio.gather(deleting, syncing)

    assert reply.status_code == 204
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    assert not folder.exists()


@pytest.mark.parametrize("id_given_out_again", [False, True])
def test_a_deleted_thread_is_not_synced_again(
    session: Session, id_given_out_again: bool
) -> None:
    """A turn that reaches its sync after the thread is deleted writes nothing.

    SQLite gives a deleted newest thread's id to the next thread, which must not
    get the deleted one's sources.
    """
    workspace_id = workspace(session)
    plan = source(session, workspace_id, "Plan", "Ship on Friday.")
    thread = agent_thread(session, workspace_id)
    session.delete(thread)
    session.commit()
    if id_given_out_again:
        next_thread = ChatThread(workspace_id=workspace_id, opencode_session_id="ses_2")
        session.add(next_thread)
        session.commit()
        assert next_thread.id == thread.id

    with pytest.raises(ThreadGoneError):
        sync_thread_folder(session, thread, [plan.id])

    folder = get_storage_settings().thread_working_dir(workspace_id, thread.id)
    assert not folder.exists()
