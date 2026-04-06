"""Tests for EtlPipelineService -- the unified ETL pipeline public interface."""

import pytest

from app.etl_pipeline.etl_document import EtlRequest
from app.etl_pipeline.etl_pipeline_service import EtlPipelineService

pytestmark = pytest.mark.unit


async def test_extract_txt_file_returns_markdown(tmp_path):
    """Tracer bullet: a .txt file is read and returned as-is in an EtlResult."""
    txt_file = tmp_path / "hello.txt"
    txt_file.write_text("Hello, world!", encoding="utf-8")

    service = EtlPipelineService()
    result = await service.extract(
        EtlRequest(file_path=str(txt_file), filename="hello.txt")
    )

    assert result.markdown_content == "Hello, world!"
    assert result.etl_service == "PLAINTEXT"
    assert result.content_type == "plaintext"


async def test_extract_md_file(tmp_path):
    """A .md file is classified as PLAINTEXT and extracted."""
    md_file = tmp_path / "readme.md"
    md_file.write_text("# Title\n\nBody text.", encoding="utf-8")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(md_file), filename="readme.md")
    )

    assert result.markdown_content == "# Title\n\nBody text."
    assert result.etl_service == "PLAINTEXT"
    assert result.content_type == "plaintext"


async def test_extract_markdown_file(tmp_path):
    """A .markdown file is classified as PLAINTEXT and extracted."""
    md_file = tmp_path / "notes.markdown"
    md_file.write_text("Some notes.", encoding="utf-8")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(md_file), filename="notes.markdown")
    )

    assert result.markdown_content == "Some notes."
    assert result.etl_service == "PLAINTEXT"


async def test_extract_python_file(tmp_path):
    """A .py source code file is classified as PLAINTEXT."""
    py_file = tmp_path / "script.py"
    py_file.write_text("print('hello')", encoding="utf-8")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(py_file), filename="script.py")
    )

    assert result.markdown_content == "print('hello')"
    assert result.etl_service == "PLAINTEXT"
    assert result.content_type == "plaintext"


async def test_extract_js_file(tmp_path):
    """A .js source code file is classified as PLAINTEXT."""
    js_file = tmp_path / "app.js"
    js_file.write_text("console.log('hi');", encoding="utf-8")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(js_file), filename="app.js")
    )

    assert result.markdown_content == "console.log('hi');"
    assert result.etl_service == "PLAINTEXT"


async def test_extract_csv_returns_markdown_table(tmp_path):
    """A .csv file is converted to a markdown table."""
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(csv_file), filename="data.csv")
    )

    assert "| name | age |" in result.markdown_content
    assert "| Alice | 30 |" in result.markdown_content
    assert result.etl_service == "DIRECT_CONVERT"
    assert result.content_type == "direct_convert"


async def test_extract_tsv_returns_markdown_table(tmp_path):
    """A .tsv file is converted to a markdown table."""
    tsv_file = tmp_path / "data.tsv"
    tsv_file.write_text("x\ty\n1\t2\n", encoding="utf-8")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(tsv_file), filename="data.tsv")
    )

    assert "| x | y |" in result.markdown_content
    assert result.etl_service == "DIRECT_CONVERT"


async def test_extract_html_returns_markdown(tmp_path):
    """An .html file is converted to markdown."""
    html_file = tmp_path / "page.html"
    html_file.write_text("<h1>Title</h1><p>Body</p>", encoding="utf-8")

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(html_file), filename="page.html")
    )

    assert "Title" in result.markdown_content
    assert "Body" in result.markdown_content
    assert result.etl_service == "DIRECT_CONVERT"


async def test_extract_mp3_returns_transcription(tmp_path, mocker):
    """An .mp3 audio file is transcribed via litellm.atranscription."""
    audio_file = tmp_path / "recording.mp3"
    audio_file.write_bytes(b"\x00" * 100)

    mocker.patch("app.config.config.STT_SERVICE", "openai/whisper-1")
    mocker.patch("app.config.config.STT_SERVICE_API_KEY", "fake-key")
    mocker.patch("app.config.config.STT_SERVICE_API_BASE", None)

    mock_transcription = mocker.patch(
        "app.etl_pipeline.parsers.audio.atranscription",
        return_value={"text": "Hello from audio"},
    )

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(audio_file), filename="recording.mp3")
    )

    assert "Hello from audio" in result.markdown_content
    assert result.etl_service == "AUDIO"
    assert result.content_type == "audio"
    mock_transcription.assert_called_once()


# ---------------------------------------------------------------------------
# Slice 7 – DOCLING document parsing
# ---------------------------------------------------------------------------


async def test_extract_pdf_with_docling(tmp_path, mocker):
    """A .pdf file with ETL_SERVICE=DOCLING returns parsed markdown."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")

    fake_docling = mocker.AsyncMock()
    fake_docling.process_document.return_value = {"content": "# Parsed PDF"}
    mocker.patch(
        "app.services.docling_service.create_docling_service",
        return_value=fake_docling,
    )

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(pdf_file), filename="report.pdf")
    )

    assert result.markdown_content == "# Parsed PDF"
    assert result.etl_service == "DOCLING"
    assert result.content_type == "document"


# ---------------------------------------------------------------------------
# Slice 8 – UNSTRUCTURED document parsing
# ---------------------------------------------------------------------------


async def test_extract_pdf_with_unstructured(tmp_path, mocker):
    """A .pdf file with ETL_SERVICE=UNSTRUCTURED returns parsed markdown."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    mocker.patch("app.config.config.ETL_SERVICE", "UNSTRUCTURED")

    class FakeDoc:
        def __init__(self, text):
            self.page_content = text

    fake_loader_instance = mocker.AsyncMock()
    fake_loader_instance.aload.return_value = [
        FakeDoc("Page 1 content"),
        FakeDoc("Page 2 content"),
    ]
    mocker.patch(
        "langchain_unstructured.UnstructuredLoader",
        return_value=fake_loader_instance,
    )

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(pdf_file), filename="report.pdf")
    )

    assert "Page 1 content" in result.markdown_content
    assert "Page 2 content" in result.markdown_content
    assert result.etl_service == "UNSTRUCTURED"
    assert result.content_type == "document"


# ---------------------------------------------------------------------------
# Slice 9 – LLAMACLOUD document parsing
# ---------------------------------------------------------------------------


async def test_extract_pdf_with_llamacloud(tmp_path, mocker):
    """A .pdf file with ETL_SERVICE=LLAMACLOUD returns parsed markdown."""
    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content " * 10)

    mocker.patch("app.config.config.ETL_SERVICE", "LLAMACLOUD")
    mocker.patch("app.config.config.LLAMA_CLOUD_API_KEY", "fake-key", create=True)

    class FakeDoc:
        text = "# LlamaCloud parsed"

    class FakeJobResult:
        pages = []

        def get_markdown_documents(self, split_by_page=True):
            return [FakeDoc()]

    fake_parser = mocker.AsyncMock()
    fake_parser.aparse.return_value = FakeJobResult()
    mocker.patch(
        "llama_cloud_services.LlamaParse",
        return_value=fake_parser,
    )
    mocker.patch(
        "llama_cloud_services.parse.utils.ResultType",
        mocker.MagicMock(MD="md"),
    )

    result = await EtlPipelineService().extract(
        EtlRequest(
            file_path=str(pdf_file), filename="report.pdf", estimated_pages=5
        )
    )

    assert result.markdown_content == "# LlamaCloud parsed"
    assert result.etl_service == "LLAMACLOUD"
    assert result.content_type == "document"


# ---------------------------------------------------------------------------
# Slice 10 – unknown extension falls through to document ETL
# ---------------------------------------------------------------------------


async def test_unknown_extension_uses_document_etl(tmp_path, mocker):
    """An allowlisted document extension (.docx) routes to the document ETL path."""
    docx_file = tmp_path / "doc.docx"
    docx_file.write_bytes(b"PK fake docx")

    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")

    fake_docling = mocker.AsyncMock()
    fake_docling.process_document.return_value = {"content": "Docx content"}
    mocker.patch(
        "app.services.docling_service.create_docling_service",
        return_value=fake_docling,
    )

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=str(docx_file), filename="doc.docx")
    )

    assert result.markdown_content == "Docx content"
    assert result.content_type == "document"


# ---------------------------------------------------------------------------
# Slice 11 – EtlRequest validation
# ---------------------------------------------------------------------------


def test_etl_request_requires_filename():
    """EtlRequest rejects missing filename."""
    with pytest.raises(Exception):
        EtlRequest(file_path="/tmp/some.txt", filename="")


# ---------------------------------------------------------------------------
# Slice 12 – unknown ETL_SERVICE raises EtlServiceUnavailableError
# ---------------------------------------------------------------------------


async def test_unknown_etl_service_raises(tmp_path, mocker):
    """An unknown ETL_SERVICE raises EtlServiceUnavailableError."""
    from app.etl_pipeline.exceptions import EtlServiceUnavailableError

    pdf_file = tmp_path / "report.pdf"
    pdf_file.write_bytes(b"%PDF fake")

    mocker.patch("app.config.config.ETL_SERVICE", "NONEXISTENT")

    with pytest.raises(EtlServiceUnavailableError, match="Unknown ETL_SERVICE"):
        await EtlPipelineService().extract(
            EtlRequest(file_path=str(pdf_file), filename="report.pdf")
        )


# ---------------------------------------------------------------------------
# Slice 13 – unsupported file types are rejected before reaching any parser
# ---------------------------------------------------------------------------


def test_unknown_extension_classified_as_unsupported():
    """An unknown extension defaults to UNSUPPORTED (allowlist behaviour)."""
    from app.etl_pipeline.file_classifier import FileCategory, classify_file

    assert classify_file("random.xyz") == FileCategory.UNSUPPORTED


@pytest.mark.parametrize("filename", [
    "malware.exe", "archive.zip", "video.mov", "font.woff2",
    "model.blend", "data.parquet", "package.deb", "firmware.bin",
])
def test_unsupported_extensions_classified_correctly(filename):
    """Extensions not in any allowlist are classified as UNSUPPORTED."""
    from app.etl_pipeline.file_classifier import FileCategory, classify_file

    assert classify_file(filename) == FileCategory.UNSUPPORTED


@pytest.mark.parametrize("filename,expected", [
    ("report.pdf", "document"),
    ("doc.docx", "document"),
    ("slides.pptx", "document"),
    ("sheet.xlsx", "document"),
    ("photo.png", "document"),
    ("photo.jpg", "document"),
    ("book.epub", "document"),
    ("letter.odt", "document"),
    ("readme.md", "plaintext"),
    ("data.csv", "direct_convert"),
])
def test_parseable_extensions_classified_correctly(filename, expected):
    """Parseable files are classified into their correct category."""
    from app.etl_pipeline.file_classifier import FileCategory, classify_file

    result = classify_file(filename)
    assert result != FileCategory.UNSUPPORTED
    assert result.value == expected


async def test_extract_unsupported_file_raises_error(tmp_path):
    """EtlPipelineService.extract() raises EtlUnsupportedFileError for .exe files."""
    from app.etl_pipeline.exceptions import EtlUnsupportedFileError

    exe_file = tmp_path / "program.exe"
    exe_file.write_bytes(b"\x00" * 10)

    with pytest.raises(EtlUnsupportedFileError, match="not supported"):
        await EtlPipelineService().extract(
            EtlRequest(file_path=str(exe_file), filename="program.exe")
        )


async def test_extract_zip_raises_unsupported_error(tmp_path):
    """EtlPipelineService.extract() raises EtlUnsupportedFileError for .zip archives."""
    from app.etl_pipeline.exceptions import EtlUnsupportedFileError

    zip_file = tmp_path / "archive.zip"
    zip_file.write_bytes(b"PK\x03\x04")

    with pytest.raises(EtlUnsupportedFileError, match="not supported"):
        await EtlPipelineService().extract(
            EtlRequest(file_path=str(zip_file), filename="archive.zip")
        )


# ---------------------------------------------------------------------------
# Slice 14 – should_skip_for_service (per-parser document filtering)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename,etl_service,expected_skip", [
    ("file.eml", "DOCLING", True),
    ("file.eml", "UNSTRUCTURED", False),
    ("file.docm", "LLAMACLOUD", False),
    ("file.docm", "DOCLING", True),
    ("file.txt", "DOCLING", False),
    ("file.csv", "LLAMACLOUD", False),
    ("file.mp3", "UNSTRUCTURED", False),
    ("file.exe", "LLAMACLOUD", True),
    ("file.pdf", "DOCLING", False),
    ("file.webp", "DOCLING", False),
    ("file.webp", "UNSTRUCTURED", True),
    ("file.gif", "LLAMACLOUD", False),
    ("file.gif", "DOCLING", True),
    ("file.heic", "UNSTRUCTURED", False),
    ("file.heic", "DOCLING", True),
    ("file.svg", "LLAMACLOUD", False),
    ("file.svg", "DOCLING", True),
    ("file.p7s", "UNSTRUCTURED", False),
    ("file.p7s", "LLAMACLOUD", True),
])
def test_should_skip_for_service(filename, etl_service, expected_skip):
    from app.etl_pipeline.file_classifier import should_skip_for_service

    assert should_skip_for_service(filename, etl_service) is expected_skip, (
        f"{filename} with {etl_service}: expected skip={expected_skip}"
    )


# ---------------------------------------------------------------------------
# Slice 14b – ETL pipeline rejects per-parser incompatible documents
# ---------------------------------------------------------------------------


async def test_extract_docm_with_docling_raises_unsupported(tmp_path, mocker):
    """Docling cannot parse .docm -- pipeline should reject before dispatching."""
    from app.etl_pipeline.exceptions import EtlUnsupportedFileError

    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")

    docm_file = tmp_path / "macro.docm"
    docm_file.write_bytes(b"\x00" * 10)

    with pytest.raises(EtlUnsupportedFileError, match="not supported by DOCLING"):
        await EtlPipelineService().extract(
            EtlRequest(file_path=str(docm_file), filename="macro.docm")
        )


async def test_extract_eml_with_docling_raises_unsupported(tmp_path, mocker):
    """Docling cannot parse .eml -- pipeline should reject before dispatching."""
    from app.etl_pipeline.exceptions import EtlUnsupportedFileError

    mocker.patch("app.config.config.ETL_SERVICE", "DOCLING")

    eml_file = tmp_path / "mail.eml"
    eml_file.write_bytes(b"From: test@example.com")

    with pytest.raises(EtlUnsupportedFileError, match="not supported by DOCLING"):
        await EtlPipelineService().extract(
            EtlRequest(file_path=str(eml_file), filename="mail.eml")
        )
