"""File type handlers for Microsoft OneDrive."""

from app.etl_pipeline.file_classifier import should_skip_for_service

ONEDRIVE_FOLDER_FACET = "folder"
ONENOTE_MIME = "application/msonenote"

SKIP_MIME_TYPES = frozenset(
    {
        ONENOTE_MIME,
        "application/vnd.ms-onenotesection",
        "application/vnd.ms-onenotenotebook",
    }
)

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
    return MIME_TO_EXTENSION.get(mime_type)


def is_folder(item: dict) -> bool:
    return ONEDRIVE_FOLDER_FACET in item


def should_skip_file(item: dict) -> tuple[bool, str | None]:
    """Skip folders, OneNote files, remote items, packages, and unsupported extensions.

    Returns (should_skip, unsupported_extension_or_None).
    The second element is only set when the skip is due to an unsupported extension.
    """
    if is_folder(item):
        return True, None
    if "remoteItem" in item:
        return True, None
    if "package" in item:
        return True, None
    mime = item.get("file", {}).get("mimeType", "")
    if mime in SKIP_MIME_TYPES:
        return True, None

    from pathlib import PurePosixPath

    from app.config import config as app_config

    name = item.get("name", "")
    if should_skip_for_service(name, app_config.ETL_SERVICE):
        ext = PurePosixPath(name).suffix.lower()
        return True, ext
    return False, None
