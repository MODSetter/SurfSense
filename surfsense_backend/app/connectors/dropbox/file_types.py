"""File type handlers for Dropbox."""

PAPER_EXTENSION = ".paper"

SKIP_EXTENSIONS: frozenset[str] = frozenset()

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


def get_extension_from_name(name: str) -> str:
    """Extract extension from filename."""
    dot = name.rfind(".")
    if dot > 0:
        return name[dot:]
    return ""


def is_folder(item: dict) -> bool:
    return item.get(".tag") == "folder"


def is_paper_file(item: dict) -> bool:
    """Detect Dropbox Paper docs (exported via /2/files/export, not /2/files/download)."""
    name = item.get("name", "")
    ext = get_extension_from_name(name).lower()
    return ext == PAPER_EXTENSION


def should_skip_file(item: dict) -> bool:
    """Skip folders and truly non-indexable files.

    Paper docs are non-downloadable but exportable, so they are NOT skipped.
    """
    if is_folder(item):
        return True
    if is_paper_file(item):
        return False
    if not item.get("is_downloadable", True):
        return True
    name = item.get("name", "")
    ext = get_extension_from_name(name).lower()
    return ext in SKIP_EXTENSIONS
