"""Where a thread's images live on disk, and the reference a stored turn keeps.

One folder per thread, each file named by its content hash, so a picture
attached twice in a thread is one file. The row keeps only the reference:
SQLite never carries the bytes.
"""

import shutil
from pathlib import Path
from typing import Any

from modules.chat.images.intake import NormalisedImage
from modules.llm.providers.types import Image
from shared.config import get_storage_settings

__all__ = [
    "image_path",
    "load",
    "referenced_keys",
    "remove_thread",
    "remove_unreferenced",
    "store",
]


def thread_dir(workspace_id: int, thread_id: int) -> Path:
    return get_storage_settings().workspace_dir(workspace_id) / "chats" / str(thread_id)


def store(image: NormalisedImage, workspace_id: int, thread_id: int) -> dict[str, Any]:
    """Write the file if it is not there yet, and return the turn's reference."""
    path = thread_dir(workspace_id, thread_id) / f"{image.sha256}{image.extension}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(image.data)
    return {
        # Relative to the data directory, as an artifact's storage key is.
        "key": path.relative_to(get_storage_settings().data_dir).as_posix(),
        "mime": image.mime,
        "size_bytes": len(image.data),
        "sha256": image.sha256,
    }


def image_path(reference: dict[str, Any]) -> Path:
    return get_storage_settings().data_dir / reference["key"]


def load(reference: dict[str, Any]) -> Image | None:
    """The stored bytes, or None when the file is gone; a turn goes on as text."""
    try:
        return Image(reference["mime"], image_path(reference).read_bytes())
    except (OSError, KeyError):
        return None


def referenced_keys(contents: list[dict[str, Any]]) -> set[str]:
    return {ref["key"] for content in contents for ref in content.get("images", [])}


def remove_unreferenced(workspace_id: int, thread_id: int, keys: set[str]) -> None:
    """Delete this thread's files no remaining turn points at."""
    folder = thread_dir(workspace_id, thread_id)
    if not folder.is_dir():
        return
    data_dir = get_storage_settings().data_dir
    for path in folder.iterdir():
        if path.relative_to(data_dir).as_posix() not in keys:
            path.unlink(missing_ok=True)


def remove_thread(workspace_id: int, thread_id: int) -> None:
    shutil.rmtree(thread_dir(workspace_id, thread_id), ignore_errors=True)
