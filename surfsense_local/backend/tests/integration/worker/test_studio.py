from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from modules.artifacts.formats import FORMATS
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from worker.studio import office, persist, run
from worker.studio.artifact import Built

pytestmark = pytest.mark.integration

SUMMARY = "# Cassini\n\nThe orbiter reached Saturn in 2004, carrying Huygens."


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database the pipeline opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


def make_artifact(
    session: Session, *, source: str = "Saturn facts.", fmt: str = "summary"
) -> Artifact:
    """A workspace with one ready source and a pending artifact over it."""
    workspace = Workspace(name="Saturn")
    session.add(workspace)
    session.flush()

    source_doc = Document(
        workspace_id=workspace.id,
        title="Facts",
        document_type=DocumentType.NOTE,
        status=DocumentStatus.READY,
        content=source,
    )
    session.add(source_doc)
    session.flush()

    document = Document(
        workspace_id=workspace.id,
        title=fmt,
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.PENDING,
    )
    session.add(document)
    session.flush()

    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace.id,
        format=fmt,
        artifact_metadata={"source_document_ids": [source_doc.id], "prompt": None},
    )
    session.add(artifact)
    session.commit()
    return artifact


def test_a_summary_becomes_ready_and_searchable(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model's markdown becomes the artifact's body and is indexed like a source."""
    monkeypatch.setattr("worker.studio.generate.generate", lambda *a, **k: SUMMARY)
    artifact = make_artifact(session)

    run(artifact.id)

    session.expire_all()
    document = artifact.document
    assert document.status is DocumentStatus.READY
    assert document.title == "Cassini"
    assert document.content == SUMMARY

    keyword = session.scalar(
        text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Huygens'")
    )
    assert keyword == 1


# One canned model reply per format. Office formats get python source the runner
# executes with the real library; builders and podcast get the JSON/markdown their
# parser expects; visual formats are drawn by the image call faked below.
_OFFICE_CODE = {
    "docx": (
        "from io import BytesIO\n"
        "from docx import Document\n"
        "d = Document()\n"
        "d.add_heading('Cassini', 0)\n"
        "d.add_paragraph('Reached Saturn in 2004.')\n"
        "buf = BytesIO()\n"
        "d.save(buf)\n"
        "output_bytes = buf.getvalue()\n"
    ),
    "pptx": (
        "from io import BytesIO\n"
        "from pptx import Presentation\n"
        "p = Presentation()\n"
        "p.slides.add_slide(p.slide_layouts[6])\n"
        "buf = BytesIO()\n"
        "p.save(buf)\n"
        "output_bytes = buf.getvalue()\n"
    ),
    "xlsx": (
        "from io import BytesIO\n"
        "import xlsxwriter\n"
        "buf = BytesIO()\n"
        "wb = xlsxwriter.Workbook(buf)\n"
        "wb.add_worksheet().write(0, 0, 'Cassini')\n"
        "wb.close()\n"
        "output_bytes = buf.getvalue()\n"
    ),
    "pdf": (
        "from io import BytesIO\n"
        "from reportlab.pdfgen import canvas\n"
        "buf = BytesIO()\n"
        "c = canvas.Canvas(buf)\n"
        "c.drawString(72, 720, 'Cassini')\n"
        "c.showPage()\n"
        "c.save()\n"
        "output_bytes = buf.getvalue()\n"
    ),
}

_BUILDER_RAW = {
    "summary": "# Cassini\n\nReached Saturn in 2004.",
    "html": '{"title": "Cassini", "sections": '
    '[{"heading": "Mission", "paragraphs": ["Reached Saturn in 2004."]}]}',
    "mindmap": '{"title": "Cassini", "nodes": '
    '[{"label": "Mission", "children": [{"label": "2004"}]}]}',
    "flashcards": '{"title": "Cassini", "cards": [{"front": "Arrival?", "back": "2004"}]}',
    "quiz": '{"title": "Cassini", "questions": '
    '[{"question": "Arrival?", "options": ["2004", "2010"], "answer": "2004"}]}',
    "podcast": '{"title": "Cassini", "turns": '
    '[{"speaker": "A", "text": "It reached Saturn in 2004."}, '
    '{"speaker": "B", "text": "Remarkable."}]}',
}

_WAV = b"RIFF" + b"\x00" * 40  # stands in for Kokoro's output.


def _openrouter_png() -> dict:
    """An OpenRouter image reply carrying one PNG as a data URL."""
    import base64

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    url = "data:image/png;base64," + base64.b64encode(png).decode()
    return {"choices": [{"message": {"images": [{"image_url": {"url": url}}]}}]}


def _fake_model(fmt: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the one external model each format reaches for, nothing more."""
    if fmt in _OFFICE_CODE:
        monkeypatch.setattr(
            "worker.studio.generate.run_model", lambda *a, **k: _OFFICE_CODE[fmt]
        )
    elif fmt in {"image", "infographic"}:
        monkeypatch.setattr(
            "worker.studio.media.visual.read_provider_key", lambda *a, **k: "key"
        )
        monkeypatch.setattr(
            "worker.studio.media.visual._request_image", lambda *a, **k: _openrouter_png()
        )
    elif fmt == "podcast":
        monkeypatch.setattr(
            "worker.studio.generate.generate", lambda *a, **k: _BUILDER_RAW["podcast"]
        )
        monkeypatch.setattr(
            "worker.studio.media.podcast.tts.synthesize", lambda turns: _WAV
        )
    else:
        monkeypatch.setattr(
            "worker.studio.generate.generate", lambda *a, **k: _BUILDER_RAW[fmt]
        )


# Formats whose deliverable is only the searchable body, with no file blob.
_BODY_ONLY = {"summary", "mindmap", "flashcards", "quiz"}


def _expected_file(fmt: str) -> tuple[str, bytes] | None:
    """The (mime, leading magic bytes) one file should carry, or None for body-only."""
    if fmt in _BODY_ONLY:
        return None
    if fmt in office.OFFICE:
        magic = b"%PDF" if fmt == "pdf" else b"PK\x03\x04"
        return office.OFFICE[fmt].mime, magic
    return {
        "html": ("text/html", b"<!doctype"),
        "image": ("image/png", b"\x89PNG"),
        "infographic": ("image/png", b"\x89PNG"),
        "podcast": ("audio/wav", b"RIFF"),
    }[fmt]


@pytest.mark.parametrize("fmt", [f.key for f in FORMATS], ids=lambda k: k)
def test_every_format_generates_to_ready(
    fmt: str, session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each catalogue format runs its real builder/code to a ready artifact.

    Only the model (and podcast TTS / image API) is faked; the builders, the
    office code runner and persistence all run for real.
    """
    _fake_model(fmt, monkeypatch)
    artifact = make_artifact(session, fmt=fmt)

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert artifact.document.content  # every format sets a searchable body

    expected = _expected_file(fmt)
    if expected is None:
        assert artifact.files == []
        return
    mime, magic = expected
    assert [file.mime_type for file in artifact.files] == [mime]
    path = get_storage_settings().data_dir / artifact.files[0].storage_key
    assert path.read_bytes().startswith(magic)


def test_a_generation_failure_leaves_a_reason(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model or builder error fails the artifact's document with why."""

    def boom(*args: object, **kwargs: object) -> str:
        raise RuntimeError("the model refused")

    monkeypatch.setattr("worker.studio.generate.generate", boom)
    artifact = make_artifact(session)

    with pytest.raises(RuntimeError, match="refused"):
        run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.FAILED
    assert "refused" in (artifact.document.error_message or "")
    assert session.scalar(text("SELECT count(*) FROM chunks")) == 0


def test_persist_stores_a_primary_blob(session: Session, stub_model: None) -> None:
    """A file format's bytes land on disk with a row that resolves back to them."""
    artifact = make_artifact(session)
    built = Built(
        title="Deck",
        markdown="# Deck\n\nOne slide.",
        primary=b"%PDF-1.7 fake",
        primary_mime="application/pdf",
    )

    persist.persist(session, artifact, artifact.document, built)
    session.commit()

    session.expire_all()
    assert len(artifact.files) == 1
    stored = artifact.files[0]
    assert stored.role is ArtifactFileRole.PRIMARY
    assert stored.size_bytes == len(built.primary)

    path = get_storage_settings().data_dir / stored.storage_key
    assert path.read_bytes() == built.primary


def test_an_artifact_deleted_before_generation_is_not_an_error(
    engine: Engine, stub_model: None
) -> None:
    """The route commits before enqueueing; a user can delete in the gap."""
    run(9999)
