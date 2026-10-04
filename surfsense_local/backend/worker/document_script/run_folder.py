"""The folder one script runs in: its script, its images, and the file it writes.

The child imports this too, so it stays free of the worker's settings and queue.
"""

import shutil
from pathlib import Path

SCRIPT_NAME = "script.py"
IMAGES_FOLDER = "images"


def prepare_run_folder(folder: Path, script: str, images: dict[str, Path]) -> None:
    """Create the folder with script.py and a copy of each image at images/<name>.png."""
    (folder / IMAGES_FOLDER).mkdir(parents=True)
    (folder / SCRIPT_NAME).write_text(script, encoding="utf-8")
    for name, source in images.items():
        shutil.copyfile(source, folder / IMAGES_FOLDER / f"{name}.png")


def require_plain_name(*names: str) -> None:
    """Refuse a name that would place a file outside the run folder."""
    for name in names:
        if not name or name in {".", ".."} or Path(name).name != name:
            raise ValueError(f"not a plain file name: {name!r}")
