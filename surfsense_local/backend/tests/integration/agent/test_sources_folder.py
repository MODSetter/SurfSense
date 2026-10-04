"""The folder of extracted text the agent reads, kept in line with the workspace's sources."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.agent.sources_folder import sync_sources_folder
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

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
    session.flush()
    return row.id


def source(
    session: Session,
    workspace_id: int,
    title: str,
    content: str,
    *,
    kind: DocumentType = DocumentType.NOTE,
    status: DocumentStatus = DocumentStatus.READY,
) -> Document:
    """A document as ingestion leaves it."""
    document = Document(
        workspace_id=workspace_id,
        title=title,
        document_type=kind,
        status=status,
        content=content,
    )
    session.add(document)
    session.commit()
    return document


def texts(folder: Path) -> dict[str, str]:
    """Each file in the sources folder, by name, with its text."""
    return {
        file.name: file.read_text(encoding="utf-8")
        for file in (folder / "sources").iterdir()
        if file.is_file()
    }


def test_each_ready_source_is_a_markdown_file_of_its_text(session: Session) -> None:
    """opencode's own tools then read what Docling extracted, not the original bytes."""
    workspace_id = workspace(session)
    upload = source(
        session,
        workspace_id,
        "report.pdf",
        "# Q3\nRevenue rose.",
        kind=DocumentType.FILE,
    )
    note = source(session, workspace_id, "Meeting notes", "Ship on Friday.")

    folder = sync_sources_folder(session, workspace_id)

    assert texts(folder) == {
        f"report.pdf [{upload.id}].md": "# Q3\nRevenue rose.",
        f"Meeting notes [{note.id}].md": "Ship on Friday.",
    }


def test_artifacts_and_sources_not_yet_ready_are_left_out(session: Session) -> None:
    """An artifact is the agent's own kind of output, and a pending file has no text yet."""
    workspace_id = workspace(session)
    source(session, workspace_id, "Quiz", "Q1?", kind=DocumentType.ARTIFACT)
    source(
        session,
        workspace_id,
        "scan.pdf",
        "",
        kind=DocumentType.FILE,
        status=DocumentStatus.PROCESSING,
    )

    folder = sync_sources_folder(session, workspace_id)

    assert texts(folder) == {}


def test_a_deleted_source_leaves_and_a_changed_one_is_rewritten(
    session: Session,
) -> None:
    """The folder follows the library: nothing stale for the agent to cite."""
    workspace_id = workspace(session)
    kept = source(session, workspace_id, "Plan", "Draft one.")
    gone = source(session, workspace_id, "Old", "Obsolete.")
    sync_sources_folder(session, workspace_id)

    kept.content = "Draft two, longer."
    session.delete(gone)
    session.commit()
    folder = sync_sources_folder(session, workspace_id)

    assert texts(folder) == {f"Plan [{kept.id}].md": "Draft two, longer."}


def test_a_change_of_the_same_length_is_still_seen(session: Session) -> None:
    """Only the bytes say a source changed; its timestamp has one-second steps."""
    workspace_id = workspace(session)
    note = source(session, workspace_id, "Plan", "Version A.")
    sync_sources_folder(session, workspace_id)

    note.content = "Version B."
    session.commit()
    folder = sync_sources_folder(session, workspace_id)

    assert texts(folder)[f"Plan [{note.id}].md"] == "Version B."


def test_a_title_cannot_reach_outside_the_folder(session: Session) -> None:
    """A title is user text; only a validated name reaches the disk."""
    workspace_id = workspace(session)
    note = source(session, workspace_id, "../../outside", "Text.")

    folder = sync_sources_folder(session, workspace_id)

    (written,) = (folder / "sources").iterdir()
    assert written.parent == folder / "sources"
    assert written.name.endswith(f"[{note.id}].md")
    assert "/" not in written.name and "\\" not in written.name


def test_two_sources_with_one_title_get_two_files(session: Session) -> None:
    """The id in each name keeps sources apart when titles collide."""
    workspace_id = workspace(session)
    source(session, workspace_id, "Notes", "First.")
    source(session, workspace_id, "Notes", "Second.")

    folder = sync_sources_folder(session, workspace_id)

    assert sorted(texts(folder).values()) == ["First.", "Second."]


def test_the_agents_outputs_survive_a_sync(session: Session) -> None:
    """The output folder is the agent's own; syncing sources never touches it."""
    workspace_id = workspace(session)
    folder = sync_sources_folder(session, workspace_id)
    (folder / "outputs" / "summary.md").write_text("Done.", encoding="utf-8")

    sync_sources_folder(session, workspace_id)

    assert (folder / "outputs" / "summary.md").read_text(encoding="utf-8") == "Done."


def test_a_deleted_sources_figures_leave_with_it(session: Session) -> None:
    """A figure the agent was shown goes when its source does, like the source's text."""
    workspace_id = workspace(session)
    kept = source(session, workspace_id, "report.pdf", "Q3", kind=DocumentType.FILE)
    gone = source(session, workspace_id, "old.pdf", "Q2", kind=DocumentType.FILE)
    folder = sync_sources_folder(session, workspace_id)
    figures = folder / "sources" / "figures"
    figures.mkdir()
    for document in (kept, gone):
        (figures / f"{document.id}-1.png").write_bytes(b"a figure")

    session.delete(gone)
    session.commit()
    sync_sources_folder(session, workspace_id)

    assert [file.name for file in figures.iterdir()] == [f"{kept.id}-1.png"]
