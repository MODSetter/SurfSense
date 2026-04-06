"""Allowlist of document extensions the ETL parsers can handle.

Every consumer (file_classifier, connector-level skip checks) imports from
here so there is a single source of truth.  Extensions already covered by
PLAINTEXT_EXTENSIONS, AUDIO_EXTENSIONS, or DIRECT_CONVERT_EXTENSIONS in
file_classifier are NOT repeated here -- this set is exclusively for the
"document" ETL path (Docling / LlamaParse / Unstructured).
"""

from pathlib import PurePosixPath

DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({
    # PDF
    ".pdf",
    # Microsoft Office
    ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    # Images (raster: OCR / vision parsing)
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif",
    # Rich text / e-book
    ".rtf", ".epub",
    # OpenDocument
    ".odt", ".ods", ".odp",
    # Other (LlamaParse / Unstructured specific)
    ".hwpx",
})


def is_supported_document_extension(filename: str) -> bool:
    """Return True if the file's extension is in the supported document set."""
    suffix = PurePosixPath(filename).suffix.lower()
    return suffix in DOCUMENT_EXTENSIONS
