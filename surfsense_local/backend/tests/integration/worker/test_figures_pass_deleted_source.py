"""A source deleted while its figures-only pass reads it.

Delete is refused only while a source is processing, so a ready source can go
mid-pass. On Windows the delete cannot remove the file Docling holds open, and
SQLite gives the deleted id to the next document, which shares its folder.
"""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api.main import create_app
from modules.documents.models import DocumentStatus
from modules.documents.tasks import extract_figures
from shared.config import get_storage_settings
from shared.db import create_session_factory
from tests.integration.worker.docling_stand_in import reading
from tests.integration.worker.test_figures import add_source, pdf_of

pytestmark = pytest.mark.integration

PICTURE = (50, 50, 110, 90)


@pytest.fixture
def ready_report(engine: Engine) -> tuple[int, int]:
    """A ready PDF with a picture for the pass to keep: its workspace and id."""
    with create_session_factory(engine)() as session:
        source = add_source(
            session, "report.pdf", pdf_of(1, (1, "red", PICTURE)), DocumentStatus.READY
        )
        return source.workspace_id, source.id


def api_over(engine: Engine) -> TestClient:
    """The routes a user deletes and uploads through, called while the pass reads."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    return TestClient(app)


def docling_doing(
    monkeypatch: pytest.MonkeyPatch, meanwhile: Callable[[], None]
) -> None:
    """Docling reads the file holding it open, as it does, while `meanwhile` runs."""

    def convert(original: Path) -> SimpleNamespace:
        with original.open("rb"):
            meanwhile()
        return SimpleNamespace(
            document=reading({"caption": "Figure 1.", "page": 1, "box": PICTURE})
        )

    monkeypatch.setattr(
        "worker.ingestion.parsing._converter",
        lambda: SimpleNamespace(convert=convert),
    )


def left_in(folder: Path) -> list[str] | None:
    """Everything under the source's folder, or None when it is gone."""
    if not folder.exists():
        return None
    return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


def test_a_source_deleted_mid_pass_leaves_no_folder_behind(
    engine: Engine, ready_report: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Its figures are not written, and the file the delete could not remove goes."""
    workspace_id, source_id = ready_report
    folder = get_storage_settings().document_dir(workspace_id, source_id)
    api = api_over(engine)

    def delete() -> None:
        deleted = api.delete(f"/workspaces/{workspace_id}/documents/{source_id}")
        assert deleted.status_code == 204

    docling_doing(monkeypatch, delete)

    extract_figures.call_local(source_id)

    assert left_in(folder) is None


def test_an_upload_given_the_deleted_id_mid_pass_keeps_only_its_own_file(
    engine: Engine, ready_report: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The new source reads its own file, not two, and none of the old figures."""
    workspace_id, source_id = ready_report
    folder = get_storage_settings().document_dir(workspace_id, source_id)
    api = api_over(engine)
    created: list[int] = []

    def delete_and_upload_another() -> None:
        api.delete(f"/workspaces/{workspace_id}/documents/{source_id}")
        uploaded = api.post(
            f"/workspaces/{workspace_id}/documents/upload",
            files={"files": ("budget.pdf", b"%PDF-1.7 budget", "application/pdf")},
        )
        created.extend(document["id"] for document in uploaded.json()["created"])

    docling_doing(monkeypatch, delete_and_upload_another)

    extract_figures.call_local(source_id)

    assert created == [source_id]  # SQLite gave the deleted id out again
    assert left_in(folder) == ["budget.pdf"]
