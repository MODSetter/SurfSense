"""Tests for the DOCUMENT_EXTENSIONS allowlist module."""

import pytest

pytestmark = pytest.mark.unit


def test_pdf_is_supported_document():
    from app.utils.file_extensions import is_supported_document_extension

    assert is_supported_document_extension("report.pdf") is True


def test_exe_is_not_supported_document():
    from app.utils.file_extensions import is_supported_document_extension

    assert is_supported_document_extension("malware.exe") is False


@pytest.mark.parametrize(
    "filename",
    [
        "report.pdf",
        "doc.docx",
        "old.doc",
        "sheet.xlsx",
        "legacy.xls",
        "slides.pptx",
        "deck.ppt",
        "macro.docm",
        "macro.xlsm",
        "macro.pptm",
        "photo.png",
        "photo.jpg",
        "photo.jpeg",
        "scan.bmp",
        "scan.tiff",
        "scan.tif",
        "photo.webp",
        "anim.gif",
        "iphone.heic",
        "manual.rtf",
        "book.epub",
        "letter.odt",
        "data.ods",
        "presentation.odp",
        "inbox.eml",
        "outlook.msg",
        "korean.hwpx",
        "korean.hwp",
        "template.dot",
        "template.dotm",
        "template.pot",
        "template.potx",
        "binary.xlsb",
        "workspace.xlw",
        "vector.svg",
        "signature.p7s",
    ],
)
def test_document_extensions_are_supported(filename):
    from app.utils.file_extensions import is_supported_document_extension

    assert is_supported_document_extension(filename) is True, (
        f"{filename} should be supported"
    )


@pytest.mark.parametrize(
    "filename",
    [
        "malware.exe",
        "archive.zip",
        "video.mov",
        "font.woff2",
        "model.blend",
        "random.xyz",
        "data.parquet",
        "package.deb",
    ],
)
def test_non_document_extensions_are_not_supported(filename):
    from app.utils.file_extensions import is_supported_document_extension

    assert is_supported_document_extension(filename) is False, (
        f"{filename} should NOT be supported"
    )


# ---------------------------------------------------------------------------
# Per-parser extension sets
# ---------------------------------------------------------------------------


def test_union_includes_all_parser_extension_sets():
    from app.utils.file_extensions import (
        AZURE_DI_DOCUMENT_EXTENSIONS,
        DOCLING_DOCUMENT_EXTENSIONS,
        DOCUMENT_EXTENSIONS,
        LLAMAPARSE_DOCUMENT_EXTENSIONS,
        UNSTRUCTURED_DOCUMENT_EXTENSIONS,
    )

    expected = (
        DOCLING_DOCUMENT_EXTENSIONS
        | LLAMAPARSE_DOCUMENT_EXTENSIONS
        | UNSTRUCTURED_DOCUMENT_EXTENSIONS
        | AZURE_DI_DOCUMENT_EXTENSIONS
    )
    assert expected == DOCUMENT_EXTENSIONS


def test_get_extensions_for_docling():
    from app.utils.file_extensions import get_document_extensions_for_service

    exts = get_document_extensions_for_service("DOCLING")
    assert ".pdf" in exts
    assert ".webp" in exts
    assert ".docx" in exts
    assert ".eml" not in exts
    assert ".docm" not in exts
    assert ".gif" not in exts
    assert ".heic" not in exts


def test_get_extensions_for_llamacloud():
    from app.utils.file_extensions import get_document_extensions_for_service

    exts = get_document_extensions_for_service("LLAMACLOUD")
    assert ".docm" in exts
    assert ".gif" in exts
    assert ".svg" in exts
    assert ".hwp" in exts
    assert ".eml" not in exts
    assert ".heic" not in exts


def test_get_extensions_for_unstructured():
    from app.utils.file_extensions import get_document_extensions_for_service

    exts = get_document_extensions_for_service("UNSTRUCTURED")
    assert ".eml" in exts
    assert ".heic" in exts
    assert ".p7s" in exts
    assert ".docm" not in exts
    assert ".gif" not in exts
    assert ".svg" not in exts


def test_get_extensions_for_none_returns_union():
    from app.utils.file_extensions import (
        DOCUMENT_EXTENSIONS,
        get_document_extensions_for_service,
    )

    assert get_document_extensions_for_service(None) == DOCUMENT_EXTENSIONS
