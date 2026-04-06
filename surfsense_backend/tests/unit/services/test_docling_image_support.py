"""Test that DoclingService registers InputFormat.IMAGE for image processing."""

from enum import Enum
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class _FakeInputFormat(Enum):
    PDF = "pdf"
    IMAGE = "image"


def test_docling_service_registers_image_format():
    """DoclingService should initialise DocumentConverter with InputFormat.IMAGE
    in allowed_formats so that image files (jpg, png, bmp, tiff) are accepted."""

    mock_converter_cls = MagicMock()
    mock_backend = MagicMock()

    fake_pipeline_options_cls = MagicMock()
    fake_pipeline_options = MagicMock()
    fake_pipeline_options_cls.return_value = fake_pipeline_options

    fake_pdf_format_option_cls = MagicMock()

    with patch.dict("sys.modules", {
        "docling": MagicMock(),
        "docling.backend": MagicMock(),
        "docling.backend.pypdfium2_backend": MagicMock(
            PyPdfiumDocumentBackend=mock_backend
        ),
        "docling.datamodel": MagicMock(),
        "docling.datamodel.base_models": MagicMock(
            InputFormat=_FakeInputFormat
        ),
        "docling.datamodel.pipeline_options": MagicMock(
            PdfPipelineOptions=fake_pipeline_options_cls
        ),
        "docling.document_converter": MagicMock(
            DocumentConverter=mock_converter_cls,
            PdfFormatOption=fake_pdf_format_option_cls,
        ),
    }):
        import app.services.docling_service as mod
        from importlib import reload
        reload(mod)

        mod.DoclingService()

    call_kwargs = mock_converter_cls.call_args
    assert call_kwargs is not None, "DocumentConverter was never called"

    _, kwargs = call_kwargs
    allowed = kwargs.get("allowed_formats")
    format_opts = kwargs.get("format_options", {})

    image_registered = (
        (allowed is not None and _FakeInputFormat.IMAGE in allowed)
        or _FakeInputFormat.IMAGE in format_opts
    )
    assert image_registered, (
        f"InputFormat.IMAGE not registered. "
        f"allowed_formats={allowed}, format_options keys={list(format_opts.keys())}"
    )
