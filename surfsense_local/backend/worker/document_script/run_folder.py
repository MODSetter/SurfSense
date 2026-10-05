"""The folder one script runs in: its script, its images, and the file it writes.

The child imports this too, so it stays free of the worker's settings and queue.
"""

import shutil
from pathlib import Path

SCRIPT_NAME = "script.py"
IMAGES_FOLDER = "images"
# The template's own suffix is kept: python-pptx and python-docx check it.
TEMPLATE_STEM = "template"


def prepare_run_folder(
    folder: Path, script: str, images: dict[str, Path], template: Path | None
) -> str | None:
    """Create the folder with script.py, a copy of each image at images/<name>.png,
    and a copy of the template; returns the template copy's name, if any.

    A copy, so whatever the script does to it never reaches the user's source.
    """
    (folder / IMAGES_FOLDER).mkdir(parents=True)
    (folder / SCRIPT_NAME).write_text(script, encoding="utf-8")
    for name, source in images.items():
        shutil.copyfile(source, folder / IMAGES_FOLDER / f"{name}.png")
    if template is None:
        return None
    name = f"{TEMPLATE_STEM}{template.suffix.lower()}"
    shutil.copyfile(template, folder / name)
    return name


def require_plain_name(*names: str) -> None:
    """Refuse a name that would place a file outside the run folder."""
    for name in names:
        if not name or name in {".", ".."} or Path(name).name != name:
            raise ValueError(f"not a plain file name: {name!r}")
