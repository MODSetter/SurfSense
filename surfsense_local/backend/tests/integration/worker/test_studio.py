import json
import time
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.providers.openai_compatible import NonRetryableImageError
from modules.llm.providers.protocols import (
    GeneratedImage,
    SpokenTurn,
    SynthesizedAudio,
    Voice,
)
from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from worker.studio import run
from worker.studio.office.docx import docx
from worker.studio.office.pdf import pdf
from worker.studio.office.pptx import pptx
from worker.studio.office.xlsx import xlsx
from worker.studio.shared import persist
from worker.studio.shared.artifact import Built

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
    options: dict | None = None,
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
        artifact_metadata={
            "source_document_ids": [source_doc.id],
            "prompt": prompt,
            "options": options,
        },
    )
    session.add(artifact)
    session.commit()
    return artifact


# Each format's test fakes only its one external model call. These helpers do
# that faking and record what the model was sent, so a test can also check that
# the user's prompt reached it.


def _capture_model(monkeypatch: pytest.MonkeyPatch, *replies: str) -> list[str]:
    """Stub the generation model to answer `replies` in turn (the last one repeats),
    recording each system prompt.

    Every builder and office format assembles its real prompt and calls
    `run_model`, so recording here lets a test assert the user's focus reached it.
    """
    seen: list[str] = []

    def fake(_session: object, system: str, _sources: object) -> str:
        seen.append(system)
        return replies[min(len(seen), len(replies)) - 1]

    monkeypatch.setattr("worker.studio.shared.generate.run_model", fake)
    return seen


def _capture_image(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stub the selected image generator, recording its content."""
    seen: list[str] = []

    class FakeImageGenerator:
        async def generate(self, _model: str, content: str) -> GeneratedImage:
            seen.append(content)
            return GeneratedImage(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "image/png")

    selection = type("Selection", (), {"provider": "fake", "name": "flux"})()
    monkeypatch.setattr(
        "worker.studio.job.resolve_image_generation",
        lambda _session: ResolvedImageGeneration(selection, FakeImageGenerator()),
    )
    return seen


def _primary_bytes(artifact: Artifact) -> bytes:
    return (
        get_storage_settings().data_dir / artifact.files[0].storage_key
    ).read_bytes()


def _one_file(artifact: Artifact, mime: str, magic: bytes) -> None:
    """The artifact holds exactly one file of `mime` whose bytes start with `magic`."""
    assert [file.mime_type for file in artifact.files] == [mime]
    assert _primary_bytes(artifact).startswith(magic)


# --- Builders: the model returns markdown/JSON, a builder renders the body. ---


def test_summary_becomes_a_searchable_markdown_body(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary: the model's markdown is the body, indexed for search, with no file."""
    seen = _capture_model(
        monkeypatch,
        "# Cassini\n\nThe orbiter reached Saturn in 2004, carrying Huygens.",
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


def test_flashcards_become_a_deck_file_and_a_study_list_body(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Flashcards: a JSON deck for the study viewer, markdown to search."""
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
    _one_file(artifact, "application/json", b"{")
    deck = json.loads(_primary_bytes(artifact))
    assert deck == {
        "schema_version": 1,
        "title": "Cassini",
        "cards": [{"front_text": "Arrival?", "back_text": "2004"}],
    }
    assert "Arrival?" in artifact.document.content
    assert "dates only" in seen[0]


def test_quiz_becomes_a_question_file_and_a_question_list_body(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quiz: a JSON quiz for the study viewer, markdown to search."""
    seen = _capture_model(
        monkeypatch,
        '{"title": "Cassini", "questions": [{"question": "Arrival?", '
        '"options": ["1997", "2004", "2010", "2017"], "answer": "2004", '
        '"explanation": "Cassini reached Saturn in July 2004."}]}',
    )
    artifact = make_artifact(session, fmt="quiz", prompt="arrival facts")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, "application/json", b"{")
    assert json.loads(_primary_bytes(artifact)) == {
        "schema_version": 1,
        "title": "Cassini",
        "questions": [
            {
                "question_text": "Arrival?",
                "options": ["1997", "2004", "2010", "2017"],
                "correct_option_index": 1,
                "explanation_text": "Cassini reached Saturn in July 2004.",
            }
        ],
    }
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
    _one_file(artifact, docx.mime, b"PK\x03\x04")
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
    _one_file(artifact, pptx.mime, b"PK\x03\x04")
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
    _one_file(artifact, xlsx.mime, b"PK\x03\x04")
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
    _one_file(artifact, pdf.mime, b"%PDF")
    assert "a cover page" in seen[0]


# --- Media: audio synthesised offline, images drawn over a BYO key. ---


def test_podcast_plans_drafts_and_voices_the_reviewed_brief(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Podcast: the brief the user reviewed reaches the pipeline; the model plans an
    outline, drafts each segment, and the voice engine voices every line."""
    seen = _capture_model(
        monkeypatch,
        '{"title": "Cassini", "segments": [{"title": "Arrival"}, {"title": "Legacy"}]}',
        '{"turns": [{"speaker": 1, "text": "It reached Saturn in 2004."}]}',
        '{"turns": [{"speaker": 2, "text": "Remarkable."}]}',
    )
    spoken: list[SpokenTurn] = []

    class FakeVoice:
        def voices(self) -> list[Voice]:
            return [
                Voice("af_heart", "Heart", "en-US"),
                Voice("am_adam", "Adam", "en-US"),
            ]

        async def synthesize(self, turns: list[SpokenTurn]) -> SynthesizedAudio:
            spoken.extend(turns)
            return SynthesizedAudio(b"RIFF" + b"\x00" * 40, "audio/wav")

    monkeypatch.setattr(
        "worker.studio.media.audio.podcast.pipeline.resolve_text_to_speech", FakeVoice
    )
    brief = {
        "language": "en-US",
        "style": "interview",
        "duration": "short",
        "speakers": [
            {"name": "Ada", "role": "host", "voice": "am_adam"},
            {"name": "Bea", "role": "expert", "voice": "af_heart"},
        ],
    }
    artifact = make_artifact(
        session, fmt="podcast", prompt="keep it short", options=brief
    )

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    _one_file(artifact, "audio/wav", b"RIFF")
    assert len(seen) == 3 and "keep it short" in seen[0] and "Ada (host)" in seen[1]
    assert [turn.voice for turn in spoken] == ["am_adam", "af_heart"]
    assert "**Bea:** Remarkable." in artifact.document.content


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


def test_a_two_model_format_gets_both_models_in_catalog_order(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Infographic declares (image_generation, generation); render gets them so."""
    _capture_image(monkeypatch)
    received: list[object] = []

    def record(*models: object, **_kwargs: object) -> Built:
        received.extend(models[:-2])  # trailing two are sources and prompt
        return Built(title="Cassini", markdown="# Cassini")

    monkeypatch.setattr(
        "worker.studio.media.visual.infographic.pipeline.render", record
    )
    artifact = make_artifact(session, fmt="infographic")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert [type(model) for model in received] == [
        ResolvedImageGeneration,
        ResolvedGeneration,
    ]


def test_a_write_during_generation_does_not_lock_the_job_out(
    session: Session, engine: Engine, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The API keeps writing while a model runs; persisting must still land."""
    artifact = make_artifact(session)

    def model_with_a_concurrent_writer(*_args: object, **_kwargs: object) -> str:
        with create_session_factory(engine)() as other:
            other.add(
                Document(
                    workspace_id=artifact.workspace_id,
                    title="typed while generating",
                    document_type=DocumentType.NOTE,
                    status=DocumentStatus.READY,
                    content="a chat turn, a new artifact, anything",
                )
            )
            other.commit()
        return SUMMARY

    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model", model_with_a_concurrent_writer
    )

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY
    assert artifact.document.content == SUMMARY


def test_studio_threads_persist_side_by_side_with_a_busy_api(
    session: Session, engine: Engine, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The studio consumer runs STUDIO_WORKERS jobs at once on the one SQLite
    file the API writes to; every job must land, none may hit a lock error."""
    from concurrent.futures import ThreadPoolExecutor

    from worker.consumer import STUDIO_WORKERS

    artifacts = [make_artifact(session) for _ in range(STUDIO_WORKERS * 2)]
    ids = [artifact.id for artifact in artifacts]
    workspace_id = artifacts[0].workspace_id

    def slow_model(*_args: object, **_kwargs: object) -> str:
        time.sleep(0.05)  # long enough for the other threads to be persisting
        return SUMMARY

    monkeypatch.setattr("worker.studio.shared.generate.run_model", slow_model)

    def api_keeps_writing() -> None:
        for n in range(40):
            with create_session_factory(engine)() as other:
                other.add(
                    Document(
                        workspace_id=workspace_id,
                        title=f"typed {n}",
                        document_type=DocumentType.NOTE,
                        status=DocumentStatus.READY,
                        content="a chat turn",
                    )
                )
                other.commit()

    with ThreadPoolExecutor(STUDIO_WORKERS + 1) as pool:
        api = pool.submit(api_keeps_writing)
        jobs = [pool.submit(run, artifact_id) for artifact_id in ids]
        for job in jobs:
            job.result()  # raises OperationalError if a lock timed out
        api.result()

    session.expire_all()
    assert all(a.document.status is DocumentStatus.READY for a in artifacts)


def test_a_generation_failure_leaves_a_reason(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model or builder error fails the artifact's document with why."""

    def boom(*args: object, **kwargs: object) -> str:
        raise RuntimeError("the model refused")

    monkeypatch.setattr("worker.studio.shared.generate.run_model", boom)
    artifact = make_artifact(session)

    with pytest.raises(RuntimeError, match="refused"):
        run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.FAILED
    # The tooltip line: what went wrong, without a Python type name in front.
    assert artifact.document.error_message == "the model refused"
    assert session.scalar(text("SELECT count(*) FROM chunks")) == 0


def test_an_image_failure_is_recorded_without_requesting_a_huey_retry(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A possibly billed image failure ends the task instead of generating twice."""

    def fail(*_args: object, **_kwargs: object) -> Built:
        raise NonRetryableImageError("image endpoint returned HTTP 500")

    monkeypatch.setattr("worker.studio.media.visual.image.pipeline.render", fail)
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
