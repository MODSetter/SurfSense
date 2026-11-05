"""The job eval reads a case's Word and PDF sources as the text ingest stores, and refuses one
ingest would give Docling or OCR, which the eval does not run."""

import docx
import pytest
from job_eval.source_files import source_text

from tests import pdf_samples
from worker.ingestion.pdf_text_layer import read_text_layer
from worker.ingestion.word_markdown import markdown_without_docling

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def switches_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default a user has: neither reader switched to Docling."""
    monkeypatch.delenv("SURFSENSE_LOCAL_DOCX_READER", raising=False)
    monkeypatch.delenv("SURFSENSE_LOCAL_PDF_TEXT_LAYER", raising=False)


def test_a_word_file_reads_as_ingest_stores_it(tmp_path):
    """The app's own Word reader, as ingest chooses it."""
    path = tmp_path / "policy.docx"
    document = docx.Document()
    document.add_paragraph("Customer data is encrypted at rest.")
    document.save(path)

    assert source_text(path, 1).text == markdown_without_docling(path)


def test_a_word_file_ingest_gives_docling_is_refused(tmp_path):
    """A file with no text goes to Docling at ingest; read here, it would give no passages."""
    path = tmp_path / "blank.docx"
    docx.Document().save(path)

    with pytest.raises(ValueError, match="with Docling"):
        source_text(path, 1)


def test_a_born_digital_pdf_reads_as_its_text_layer(tmp_path):
    """The exact text ingest stores, its paragraph breaks included."""
    path = tmp_path / "policy.pdf"
    path.write_bytes(pdf_samples.text_pages(pdf_samples.prose(6, seed=1)))

    assert source_text(path, 1).text == read_text_layer(path).text


def test_a_scanned_pdf_is_refused(tmp_path):
    """Ingest reads a scan with OCR; its empty text layer would give no passages."""
    path = tmp_path / "scan.pdf"
    path.write_bytes(
        pdf_samples.scanned_page(pdf_samples.prose(3, seed=2), ocr_layer=False)
    )

    with pytest.raises(ValueError, match="with OCR or Docling"):
        source_text(path, 1)
