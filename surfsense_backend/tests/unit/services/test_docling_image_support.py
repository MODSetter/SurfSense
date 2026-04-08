"""Test that DoclingService does NOT restrict allowed_formats, letting Docling
accept all its supported formats (PDF, DOCX, PPTX, XLSX, IMAGE, etc.)."""

from enum import Enum
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class _FakeInputFormat(Enum):
    PDF = "pdf"
    IMAGE = "image"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"


def test_docling_service_does_not_restrict_allowed_formats():
    """DoclingService should NOT pass allowed_formats to DocumentConverter,
    so Docling defaults to accepting every InputFormat it supports."""

    mock_converter_cls = MagicMock()
    mock_backend = MagicMock()

    fake_pipeline_options_cls = MagicMock()
    fake_pipeline_options = MagicMock()
    fake_pipeline_options_cls.return_value = fake_pipeline_options

    fake_pdf_format_option_cls = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "docling": MagicMock(),
            "docling.backend": MagicMock(),
            "docling.backend.pypdfium2_backend": MagicMock(
                PyPdfiumDocumentBackend=mock_backend
            ),
            "docling.datamodel": MagicMock(),
            "docling.datamodel.base_models": MagicMock(InputFormat=_FakeInputFormat),
            "docling.datamodel.pipeline_options": MagicMock(
                PdfPipelineOptions=fake_pipeline_options_cls
            ),
            "docling.document_converter": MagicMock(
                DocumentConverter=mock_converter_cls,
                PdfFormatOption=fake_pdf_format_option_cls,
            ),
        },
    ):
        from importlib import reload

        import app.services.docling_service as mod

        reload(mod)

        mod.DoclingService()

    call_kwargs = mock_converter_cls.call_args
    assert call_kwargs is not None, "DocumentConverter was never called"

    _, kwargs = call_kwargs
    assert "allowed_formats" not in kwargs, (
        f"allowed_formats should not be passed — let Docling accept all formats. "
        f"Got: {kwargs.get('allowed_formats')}"
    )
    assert _FakeInputFormat.PDF in kwargs.get("format_options", {}), (
        "format_options should still configure PDF pipeline options"
    )
