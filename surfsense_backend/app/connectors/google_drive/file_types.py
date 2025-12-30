"""File type handlers for Google Drive."""

GOOGLE_DOC = "application/vnd.google-apps.document"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE = "application/vnd.google-apps.presentation"
GOOGLE_FOLDER = "application/vnd.google-apps.folder"
GOOGLE_SHORTCUT = "application/vnd.google-apps.shortcut"

EXPORT_FORMATS = {
    GOOGLE_DOC: "application/pdf",
    GOOGLE_SHEET: "application/pdf",
    GOOGLE_SLIDE: "application/pdf",
}


def is_google_workspace_file(mime_type: str) -> bool:
    """Check if file is a Google Workspace file that needs export."""
    return mime_type.startswith("application/vnd.google-apps")


def should_skip_file(mime_type: str) -> bool:
    """Check if file should be skipped (folders, shortcuts, etc)."""
    return mime_type in [GOOGLE_FOLDER, GOOGLE_SHORTCUT]


def get_export_mime_type(mime_type: str) -> str | None:
    """Get export MIME type for Google Workspace files."""
    return EXPORT_FORMATS.get(mime_type)
