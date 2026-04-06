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


def should_skip_file(item: dict) -> bool:
    """Skip folders, OneNote files, remote items (shared links), packages, and unsupported extensions."""
    if is_folder(item):
        return True
    if "remoteItem" in item:
        return True
    if "package" in item:
        return True
    mime = item.get("file", {}).get("mimeType", "")
    if mime in SKIP_MIME_TYPES:
        return True
    from app.config import config as app_config

    name = item.get("name", "")
    return should_skip_for_service(name, app_config.ETL_SERVICE)
