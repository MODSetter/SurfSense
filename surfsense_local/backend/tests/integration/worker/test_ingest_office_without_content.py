"""Office files with nothing to read, such as a template, ingested with real Docling,
and which of Docling's failures are tried again."""

import io
import zipfile
from collections.abc import Iterator

import pytest
from docx import Document as WordDocument
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.source_figures.layout import figures_dir, read_index
from modules.documents.tasks import ingest_document
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from shared.queue import ingest_queue
from worker.ingestion import run

pytestmark = pytest.mark.integration


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database ingest opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


def upload(session: Session, name: str, content: bytes) -> Document:
    """A pending uploaded file with its original on disk, as the upload route leaves it."""
    workspace = Workspace(name="Brand")
    session.add(workspace)
    session.flush()
    document = Document(
        workspace_id=workspace.id,
        title=name,
        document_type=DocumentType.FILE,
        dedup_key=name,
        document_metadata={"suffix": name[name.rindex(".") :]},
    )
    session.add(document)
    session.commit()
    folder = get_storage_settings().document_dir(workspace.id, document.id)
    folder.mkdir(parents=True)
    (folder / name).write_bytes(content)
    return document


def saved(office_file: object) -> bytes:
    """A python-docx, python-pptx or openpyxl file's bytes."""
    buffer = io.BytesIO()
    office_file.save(buffer)  # type: ignore[attr-defined]
    return buffer.getvalue()


def template_deck() -> bytes:
    """A widescreen template with renamed layouts and no slides, as PowerPoint saves one."""
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    deck.slide_layouts[0].name = "Brand_Title"
    deck.slide_layouts[1].name = "Brand Content"
    return saved(deck)


def test_a_deck_with_no_slides_is_a_ready_template(
    session: Session, stub_model: None
) -> None:
    """Docling refuses a deck with no pages; a template must still be usable."""
    document = upload(session, "brand.pptx", template_deck())

    run(document.id)

    session.expire_all()
    assert document.status is DocumentStatus.READY
    assert document.error_message is None
    content = document.content or ""
    assert content.startswith("PowerPoint template with no slides.")
    assert "13.33 x 7.5 in (16:9)" in content
    # Exact names, in order, so the agent can pick a layout by name.
    assert content.index("- Brand_Title") < content.index("- Brand Content")
    assert "- Title Only" in content

    found = session.scalar(
        text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'template'")
    )
    assert found == 1
    # No pictures to keep, recorded so the figures-only pass never reads it again.
    folder = figures_dir(
        get_storage_settings().document_dir(document.workspace_id, document.id)
    )
    assert read_index(folder) == []


def test_a_layout_name_with_a_line_break_stays_one_layout(
    session: Session, stub_model: None
) -> None:
    """A break inside a name must not read as a heading or another layout."""
    deck = Presentation()
    deck.slide_layouts[0].name = "Brand\n\n# Cover\r\n- Wide"
    document = upload(session, "brand.pptx", saved(deck))

    run(document.id)

    session.expire_all()
    content = document.content or ""
    assert "- Brand # Cover - Wide\n- Title and Content" in content
    assert "\n#" not in content


def test_a_deck_with_slides_is_still_read_by_docling(
    session: Session, stub_model: None
) -> None:
    """Only a deck with no slides at all is described rather than read."""
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Harbour budget"
    slide.placeholders[1].text = "Ferry subsidy rises 4 percent."
    document = upload(session, "budget.pptx", saved(deck))

    run(document.id)

    session.expire_all()
    assert document.status is DocumentStatus.READY
    assert "Ferry subsidy rises 4 percent." in (document.content or "")
    assert "template" not in (document.content or "")


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("blank.docx", lambda: saved(WordDocument())),
        ("blank.xlsx", lambda: saved(Workbook())),
    ],
)
def test_a_blank_word_or_excel_file_is_ready(
    session: Session, stub_model: None, name: str, content: object
) -> None:
    """Docling reads these as empty rather than refusing them."""
    document = upload(session, name, content())  # type: ignore[operator]

    run(document.id)

    session.expire_all()
    assert document.status is DocumentStatus.READY


def test_a_file_docling_refuses_fails_without_retries(
    session: Session, stub_model: None
) -> None:
    """The same bytes are refused again, so a retry would only delay the failed state."""
    broken = io.BytesIO()
    with zipfile.ZipFile(broken, "w") as package:
        package.writestr("word/document.xml", "<not word")
    document = upload(session, "broken.docx", broken.getvalue())

    ingest_document(document.id)
    ingest_queue.execute(ingest_queue.dequeue())

    session.expire_all()
    assert document.status is DocumentStatus.FAILED
    assert "could not load document" in (document.error_message or "")
    assert ingest_queue.pending_count() == 0
    assert ingest_queue.scheduled_count() == 0


def damaged(package: bytes, part: str) -> bytes:
    """The package with one part's compressed bytes scrambled, as a bad disk or download leaves it."""
    raw = bytearray(package)
    with zipfile.ZipFile(io.BytesIO(package)) as opened:
        entry = opened.getinfo(part)
    start = entry.header_offset + 30 + len(entry.filename.encode()) + len(entry.extra)
    for at in range(start + 2, start + min(40, entry.compress_size)):
        raw[at] ^= 0xFF
    return bytes(raw)


def test_a_damaged_deck_is_refused_by_docling_without_retries(
    session: Session, stub_model: None
) -> None:
    """Telling a template from a deck must not fail first: Docling says why."""
    document = upload(
        session, "damaged.pptx", damaged(template_deck(), "ppt/presentation.xml")
    )

    ingest_document(document.id)
    ingest_queue.execute(ingest_queue.dequeue())

    session.expire_all()
    assert document.status is DocumentStatus.FAILED
    assert (document.error_message or "").startswith("UnreadableFileError")
    assert ingest_queue.pending_count() == 0
    assert ingest_queue.scheduled_count() == 0


def test_a_file_another_program_holds_open_is_tried_again(
    session: Session, stub_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Docling reports a file it cannot open yet like one it refuses; only the refusal is final."""
    from docling.datamodel import document as docling_input

    reads = docling_input.create_file_hash
    held = [True]

    def sharing_violation(path: object) -> str:
        if held.pop() if held else False:
            raise PermissionError(13, "The file is in use by another process")
        return reads(path)

    monkeypatch.setattr(docling_input, "create_file_hash", sharing_violation)
    document = upload(session, "letter.docx", saved(WordDocument()))

    ingest_document(document.id)
    ingest_queue.execute(ingest_queue.dequeue())

    session.expire_all()
    assert document.status is DocumentStatus.FAILED
    assert ingest_queue.pending_count() == 1
    session.rollback()  # the retry writes the row this read holds

    ingest_queue.execute(ingest_queue.dequeue())

    session.expire_all()
    assert document.status is DocumentStatus.READY
