"""What is in audio.cpp's folder, by name."""

from pathlib import Path


def files_in(folder: Path | None) -> set[str]:
    if folder is None or not folder.is_dir():
        return set()
    return {p.name for p in folder.iterdir()}
