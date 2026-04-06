"""File type handlers for Google Drive."""

from app.etl_pipeline.file_classifier import FileCategory, classify_file

GOOGLE_DOC = "application/vnd.google-apps.document"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE = "application/vnd.google-apps.presentation"
GOOGLE_FOLDER = "application/vnd.google-apps.folder"
GOOGLE_SHORTCUT = "application/vnd.google-apps.shortcut"

EXPORT_FORMATS = {
    GOOGLE_DOC: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    GOOGLE_SHEET: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    GOOGLE_SLIDE: "application/pdf",
}

MIME_TO_EXTENSION: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.ms-excel": ".xls",
    "application/msword": ".doc",
    "application/vnd.ms-powerpoint": ".ppt",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/html": ".html",
    "text/markdown": ".md",
    "application/json": ".json",
    "application/xml": ".xml",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}


def get_extension_from_mime(mime_type: str) -> str | None:
    """Return a file extension (with leading dot) for a MIME type, or None."""
    return MIME_TO_EXTENSION.get(mime_type)


def is_google_workspace_file(mime_type: str) -> bool:
    """Check if file is a Google Workspace file that needs export."""
    return mime_type.startswith("application/vnd.google-apps")


def should_skip_file(mime_type: str) -> bool:
    """Check if file should be skipped (folders, shortcuts, etc)."""
    return mime_type in [GOOGLE_FOLDER, GOOGLE_SHORTCUT]


def should_skip_by_extension(filename: str) -> bool:
    """Return True if the file extension is not parseable by any ETL pipeline."""
    return classify_file(filename) == FileCategory.UNSUPPORTED


def get_export_mime_type(mime_type: str) -> str | None:
    """Get export MIME type for Google Workspace files."""
    return EXPORT_FORMATS.get(mime_type)
