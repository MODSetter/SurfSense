"""The figures a source offers documents, as the agent's tools reach them."""

import io
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.source_figures import (
    FiguresPending,
    SourceFigure,
    figure_file,
    list_figures,
)
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from shared.queue import ingest_queue

pytestmark = pytest.mark.integration


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database the routes use too."""
    with create_session_factory(engine)() as opened:
        yield opened


@pytest.fixture
def workspace(session: Session) -> Workspace:
    """The workspace every source here belongs to."""
    created = Workspace(name="Proposals")
    session.add(created)
    session.commit()
    return created


def add_source(
    session: Session,
    workspace: Workspace,
    filename: str = "Brand kit.pdf",
    status: DocumentStatus = DocumentStatus.READY,
) -> Document:
    """A FILE source with its original on disk, as an upload leaves it."""
    source = Document(
        workspace_id=workspace.id,
        title=filename,
        document_type=DocumentType.FILE,
        status=status,
    )
    session.add(source)
    session.commit()
    folder = get_storage_settings().document_dir(workspace.id, source.id)
    folder.mkdir(parents=True)
    (folder / filename).write_bytes(b"%PDF-1.7 fake")
    return source


def keep(source: Document, *figures: dict) -> Path:
    """Lay figures out beside the original as ingest keeps them."""
    folder = get_storage_settings().document_dir(source.workspace_id, source.id)
    figures_dir = folder / "figures"
    figures_dir.mkdir()
    for entry in figures:
        png = io.BytesIO()
        Image.new("RGB", (entry["width"], entry["height"]), "red").save(png, "PNG")
        (figures_dir / f"{entry['n']}.png").write_bytes(png.getvalue())
    (figures_dir / "figures.json").write_text(
        json.dumps({"version": 1, "figures": list(figures)}), encoding="utf-8"
    )
    return figures_dir


LOGO = {"n": 1, "caption": "Our logo", "page": 1, "width": 40, "height": 20}
CHART = {"n": 2, "caption": None, "page": 3, "width": 64, "height": 48}


def queued() -> list[tuple[str, tuple]]:
    """The ingest jobs waiting, as task name and arguments."""
    return [(task.name, task.args) for task in ingest_queue.pending()]


def test_a_sources_figures_are_listed_by_name(
    session: Session, workspace: Workspace
) -> None:
    """A name is what a document script asks for, so it carries the source's id."""
    source = add_source(session, workspace)
    keep(source, LOGO, CHART)

    figures = list_figures(session, workspace.id, source.id)

    assert figures == [
        SourceFigure(f"{source.id}-1", source.id, "Our logo", 1, 40, 20),
        SourceFigure(f"{source.id}-2", source.id, None, 3, 64, 48),
    ]


def test_a_source_ingested_before_figures_were_kept_queues_their_extraction(
    session: Session, workspace: Workspace
) -> None:
    """Asking again while the pass waits in the queue does not queue it twice."""
    source = add_source(session, workspace)

    for _ in range(2):
        with pytest.raises(FiguresPending):
            list_figures(session, workspace.id, source.id)

    assert queued() == [("extract_figures", (source.id,))]


def test_a_source_still_being_ingested_waits_for_its_own_ingest(
    session: Session, workspace: Workspace
) -> None:
    """Ingest keeps figures itself, so a second reading of the file would be waste."""
    source = add_source(session, workspace, status=DocumentStatus.PROCESSING)

    with pytest.raises(FiguresPending):
        list_figures(session, workspace.id, source.id)

    assert queued() == []


def test_sources_that_hold_no_figures_list_none(
    session: Session, workspace: Workspace
) -> None:
    """Notes, Studio outputs, plain text and failed sources have nothing to extract."""
    note = Document(
        workspace_id=workspace.id,
        title="Ideas",
        document_type=DocumentType.NOTE,
        content="text",
        status=DocumentStatus.READY,
    )
    session.add(note)
    session.commit()
    text = add_source(session, workspace, filename="notes.md")
    failed = add_source(
        session, workspace, filename="broken.pdf", status=DocumentStatus.FAILED
    )

    for source in (note, text, failed):
        assert list_figures(session, workspace.id, source.id) == []
    assert queued() == []


def test_figures_whose_extraction_failed_list_none(
    session: Session, workspace: Workspace
) -> None:
    """The failure is recorded in the index, so the pass is not queued forever."""
    source = add_source(session, workspace)
    figures_dir = keep(source)
    (figures_dir / "figures.json").write_text(
        json.dumps({"version": 1, "figures": [], "error": "OSError: disk full"}),
        encoding="utf-8",
    )

    assert list_figures(session, workspace.id, source.id) == []
    assert queued() == []


def test_another_workspaces_source_is_not_listed(
    session: Session, workspace: Workspace
) -> None:
    """A source id alone must not reach across workspaces."""
    source = add_source(session, workspace)
    keep(source, LOGO)
    other = Workspace(name="Other")
    session.add(other)
    session.commit()

    with pytest.raises(LookupError):
        list_figures(session, other.id, source.id)


def test_a_figure_name_resolves_to_its_png(
    session: Session, workspace: Workspace
) -> None:
    """What the runner copies into a script's images folder."""
    source = add_source(session, workspace)
    figures_dir = keep(source, LOGO, CHART)

    path = figure_file(session, workspace.id, f"{source.id}-2")

    assert path == figures_dir / "2.png"
    with Image.open(path) as image:
        assert image.size == (64, 48)


def test_a_figure_from_another_workspace_is_refused(
    session: Session, workspace: Workspace
) -> None:
    """A script names images by string, so the name alone must not cross workspaces."""
    source = add_source(session, workspace)
    keep(source, LOGO)
    other = Workspace(name="Other")
    session.add(other)
    session.commit()

    with pytest.raises(LookupError):
        figure_file(session, other.id, f"{source.id}-1")


@pytest.mark.parametrize(
    "name",
    [
        "{id}-1/../../{id}-1",
        "../{id}-1",
        "{id}-1.png",
        "{id}-..",
        "{id}--1",
        "{id}-1\x00",
        "{id}-\u0661",  # an Arabic-Indic one, which int() would accept
        "{id}",
        "",
    ],
)
def test_a_name_that_is_not_a_figure_name_is_refused(
    session: Session, workspace: Workspace, name: str
) -> None:
    """A model writes the name, so nothing but `<id>-<n>` may come near a path."""
    source = add_source(session, workspace)
    keep(source, LOGO)

    with pytest.raises(LookupError):
        figure_file(session, workspace.id, name.format(id=source.id))


def test_a_figure_the_index_does_not_list_or_the_disk_lost_is_refused(
    session: Session, workspace: Workspace
) -> None:
    """Refused by name, rather than failing later inside the script."""
    source = add_source(session, workspace)
    figures_dir = keep(source, LOGO, CHART)
    (figures_dir / "2.png").unlink()

    for name in (f"{source.id}-2", f"{source.id}-3"):
        with pytest.raises(LookupError):
            figure_file(session, workspace.id, name)


async def test_deleting_a_source_removes_its_figures(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """Figures live in the source's folder, which the delete route removes whole."""
    source = add_source(session, workspace)
    figures_dir = keep(source, LOGO)

    deleted = await client.delete(f"/workspaces/{workspace.id}/documents/{source.id}")

    assert deleted.status_code == 204
    assert not figures_dir.exists()
