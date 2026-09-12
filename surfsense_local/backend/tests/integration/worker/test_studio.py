from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.providers.openai_compatible import NonRetryableImageError
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import ResolvedImageGeneration
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
    session: Session,
    *,
    source: str = "Saturn facts.",
    fmt: str = "summary",
    prompt: str | None = None,
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
        artifact_metadata={"source_document_ids": [source_doc.id], "prompt": prompt},
    )
    session.add(artifact)
    session.commit()
    return artifact


# Each format's test fakes only its one external model call. These helpers do
# that faking and record what the model was sent, so a test can also check that
# the user's prompt reached it.


def _capture_model(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[str]:
    """Stub the generation model to return `reply`, recording each system prompt.

    Every builder and office format assembles its real prompt and calls
    `run_model`, so recording here lets a test assert the user's focus reached it.
    """
    seen: list[str] = []

    def fake(_session: object, system: str, _sources: object) -> str:
        seen.append(system)
        return reply

    monkeypatch.setattr("worker.studio.generate.run_model", fake)
    return seen


def _capture_image(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stub the selected image generator, recording its content."""
    seen: list[str] = []

    class FakeImageGenerator:
        async def generate(self, _model: str, content: str) -> GeneratedImage:
            seen.append(content)
            return GeneratedImage(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "image/png")

    selection = type("Selection", (), {"name": "flux"})()
    monkeypatch.setattr(
        "worker.studio.media.image.resolve_image_generation",
        lambda _session: ResolvedImageGeneration(selection, FakeImageGenerator()),
    )
    return seen


def _one_file(artifact: Artifact, mime: str, magic: bytes) -> None:
    """The artifact holds exactly one file of `mime` whose bytes start with `magic`."""
    assert [file.mime_type for file in artifact.files] == [mime]
    path = get_storage_settings().data_dir / artifact.files[0].storage_key
    assert path.read_bytes().startswith(magic)


# --- Builders: the model returns markdown/JSON, a builder renders the body. ---


def test_summary_becomes_a_searchable_markdown_body(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary: the model's markdown is the body, indexed for search, with no file."""
    seen = _capture_model(
        monkeypatch, "# Cassini\n\nThe orbiter reached Saturn in 2004, carrying Huygens."
    )
    artifact = make_artifact(session, fmt="summary", prompt="the arrival date")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert artifact.document.title == "Cassini"
    assert artifact.files == []
    assert "the arrival date" in seen[0]  # the user's focus reached the model
    keyword = session.scalar(
        text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Huygens'")
    )
    assert keyword == 1


def test_html_becomes_a_self_contained_web_page(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Web page: the model's JSON sections render to one escaped HTML file."""
    seen = _capture_model(
        monkeypatch,
        '{"title": "Cassini", "sections": '
        '[{"heading": "Mission", "paragraphs": ["Reached Saturn in 2004."]}]}',
    )
    artifact = make_artifact(session, fmt="html", prompt="the mission timeline")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, "text/html", b"<!doctype")
    assert "the mission timeline" in seen[0]


def test_mindmap_becomes_a_nested_outline_body(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mind map: the model's node tree becomes a nested markdown outline, no file."""
    seen = _capture_model(
        monkeypatch,
        '{"title": "Cassini", "nodes": '
        '[{"label": "Mission", "children": [{"label": "2004"}]}]}',
    )
    artifact = make_artifact(session, fmt="mindmap", prompt="key milestones")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert artifact.files == []
    assert "- Mission" in artifact.document.content
    assert "key milestones" in seen[0]


def test_flashcards_become_a_study_list_body(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Flashcards: the model's front/back pairs render to a markdown list, no file."""
    seen = _capture_model(
        monkeypatch,
        '{"title": "Cassini", "cards": [{"front": "Arrival?", "back": "2004"}]}',
    )
    artifact = make_artifact(session, fmt="flashcards", prompt="dates only")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert artifact.files == []
    assert "Arrival?" in artifact.document.content
    assert "dates only" in seen[0]


def test_quiz_becomes_a_question_list_body(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quiz: the model's multiple-choice questions render to a markdown body, no file."""
    seen = _capture_model(
        monkeypatch,
        '{"title": "Cassini", "questions": '
        '[{"question": "Arrival?", "options": ["2004", "2010"], "answer": "2004"}]}',
    )
    artifact = make_artifact(session, fmt="quiz", prompt="arrival facts")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert artifact.files == []
    assert "Answer: 2004" in artifact.document.content
    assert "arrival facts" in seen[0]


# --- Office: the model writes library code the runner executes to a real file. ---

_DOCX_CODE = (
    "from io import BytesIO\n"
    "from docx import Document\n"
    "d = Document()\n"
    "d.add_heading('Cassini', 0)\n"
    "d.add_paragraph('Reached Saturn in 2004.')\n"
    "buf = BytesIO()\n"
    "d.save(buf)\n"
    "output_bytes = buf.getvalue()\n"
)

_PPTX_CODE = (
    "from io import BytesIO\n"
    "from pptx import Presentation\n"
    "p = Presentation()\n"
    "p.slides.add_slide(p.slide_layouts[6])\n"
    "buf = BytesIO()\n"
    "p.save(buf)\n"
    "output_bytes = buf.getvalue()\n"
)

_XLSX_CODE = (
    "from io import BytesIO\n"
    "import xlsxwriter\n"
    "buf = BytesIO()\n"
    "wb = xlsxwriter.Workbook(buf)\n"
    "wb.add_worksheet().write(0, 0, 'Cassini')\n"
    "wb.close()\n"
    "output_bytes = buf.getvalue()\n"
)

_PDF_CODE = (
    "from io import BytesIO\n"
    "from reportlab.pdfgen import canvas\n"
    "buf = BytesIO()\n"
    "c = canvas.Canvas(buf)\n"
    "c.drawString(72, 720, 'Cassini')\n"
    "c.showPage()\n"
    "c.save()\n"
    "output_bytes = buf.getvalue()\n"
)


def test_docx_runs_generated_python_docx_code(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Document: the model's python-docx code runs to a real .docx (a zip)."""
    seen = _capture_model(monkeypatch, _DOCX_CODE)
    artifact = make_artifact(session, fmt="docx", prompt="a one-page brief")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, office.OFFICE["docx"].mime, b"PK\x03\x04")
    assert "a one-page brief" in seen[0]


def test_pptx_runs_generated_python_pptx_code(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Slides: the model's python-pptx code runs to a real .pptx (a zip)."""
    seen = _capture_model(monkeypatch, _PPTX_CODE)
    artifact = make_artifact(session, fmt="pptx", prompt="three slides")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, office.OFFICE["pptx"].mime, b"PK\x03\x04")
    assert "three slides" in seen[0]


def test_xlsx_runs_generated_xlsxwriter_code(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spreadsheet: the model's XlsxWriter code runs to a real .xlsx (a zip)."""
    seen = _capture_model(monkeypatch, _XLSX_CODE)
    artifact = make_artifact(session, fmt="xlsx", prompt="one column")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, office.OFFICE["xlsx"].mime, b"PK\x03\x04")
    assert "one column" in seen[0]


def test_pdf_runs_generated_reportlab_code(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PDF: the model's ReportLab code runs to a real .pdf."""
    seen = _capture_model(monkeypatch, _PDF_CODE)
    artifact = make_artifact(session, fmt="pdf", prompt="a cover page")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, office.OFFICE["pdf"].mime, b"%PDF")
    assert "a cover page" in seen[0]


# --- Media: audio synthesised offline, images drawn over a BYO key. ---


def test_podcast_synthesizes_a_wav_from_the_transcript(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Podcast: the model writes a two-host transcript, Kokoro renders it to WAV."""
    seen = _capture_model(
        monkeypatch,
        '{"title": "Cassini", "turns": '
        '[{"speaker": "A", "text": "It reached Saturn in 2004."}, '
        '{"speaker": "B", "text": "Remarkable."}]}',
    )
    monkeypatch.setattr(
        "worker.studio.media.podcast.tts.synthesize", lambda turns: b"RIFF" + b"\x00" * 40
    )
    artifact = make_artifact(session, fmt="podcast", prompt="keep it short")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, "audio/wav", b"RIFF")
    assert "keep it short" in seen[0]


def test_image_draws_a_png_over_the_selected_connection(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Image: the selected remote model's bytes become the primary file."""
    seen = _capture_image(monkeypatch)
    artifact = make_artifact(session, fmt="image", prompt="a bright poster")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, "image/png", b"\x89PNG")
    assert "a bright poster" in seen[0]


def test_infographic_builds_a_deterministic_svg(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Infographic: a chat model returns facts and the builder renders safe SVG."""
    seen = _capture_model(
        monkeypatch,
        '{"title":"Cassini","summary":"Saturn mission",'
        '"sections":[{"label":"Arrival","value":"2004","detail":"Reached Saturn"}]}',
    )
    artifact = make_artifact(session, fmt="infographic", prompt="the key figures")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, "image/svg+xml", b"<svg")
    assert "the key figures" in seen[0]


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


def test_an_image_failure_is_recorded_without_requesting_a_huey_retry(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A possibly billed image failure ends the task instead of generating twice."""

    def fail(*_args: object, **_kwargs: object) -> Built:
        raise NonRetryableImageError("image endpoint returned HTTP 500")

    monkeypatch.setattr("worker.studio.media.render", fail)
    artifact = make_artifact(session, fmt="image")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.FAILED
    assert "HTTP 500" in (artifact.document.error_message or "")


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
