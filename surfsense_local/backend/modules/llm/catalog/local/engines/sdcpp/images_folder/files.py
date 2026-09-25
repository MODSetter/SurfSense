"""What is in sd-server's folder, by name, the files models share included."""

from pathlib import Path

from modules.llm.catalog.local.engines.sdcpp.images_folder.landing import SHARED


def files_in(folder: Path | None) -> set[str]:
    if folder is None or not folder.is_dir():
        return set()
    names = {p.name for p in folder.iterdir()}
    shared = folder / SHARED
    if shared.is_dir():
        names |= {f"{SHARED}/{p.name}" for p in shared.iterdir()}
    return names
