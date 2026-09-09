from pathlib import Path

from shared.config import get_storage_settings

PARSER_DIR_NAME = "docling"
PARSER_FOLDERS = (
    "docling-project--docling-layout-heron",
    "docling-project--docling-models",
    "RapidOcr",
)


def parser_dir(models_dir: Path | None = None) -> Path:
    root = models_dir if models_dir is not None else get_storage_settings().models_dir
    return root / PARSER_DIR_NAME


def missing_parser_folders(models_dir: Path | None = None) -> list[str]:
    """Folders a development install still needs before a PDF can stay offline."""
    directory = parser_dir(models_dir)
    return [name for name in PARSER_FOLDERS if not _folder_ready(directory / name)]


def _folder_ready(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())
