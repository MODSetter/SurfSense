"""The folder an analysis script runs in: its script, read-only copies of its inputs, and an empty output folder."""

import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from worker.document_script.run_folder import SCRIPT_NAME

INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class AnalysisInput:
    """One source's original file, only ever read, and the name its copy takes."""

    path: Path
    name: str
    document_id: int
    title: str


def prepare_analysis_folder(
    folder: Path, script: str, inputs: list[AnalysisInput]
) -> None:
    """Write script.py, copy each input into input/ read-only beside a manifest, and make output/.

    A copy, so whatever the script does to it never reaches the user's source.
    """
    input_dir = folder / INPUT_FOLDER
    input_dir.mkdir(parents=True)
    (folder / OUTPUT_FOLDER).mkdir()
    (folder / SCRIPT_NAME).write_text(script, encoding="utf-8")
    manifest = []
    taken: set[str] = {MANIFEST_NAME.casefold()}
    for source in inputs:
        name = _unique_name(source, taken)
        copy = input_dir / name
        shutil.copyfile(source.path, copy)
        os.chmod(copy, stat.S_IREAD)
        manifest.append(
            {"file": name, "document_id": source.document_id, "title": source.title}
        )
    (input_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def remove_analysis_folder(folder: Path) -> None:
    """Delete the folder; Windows refuses to delete a read-only file until it is made writable."""

    def make_writable_and_retry(function, path, _error) -> None:
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            function(path)
        except OSError:
            pass

    shutil.rmtree(folder, onexc=make_writable_and_retry)


def _unique_name(source: AnalysisInput, taken: set[str]) -> str:
    """The file's own name, or with ` [<id>]` before its suffix when another input has it."""
    name = source.name
    if name.casefold() in taken:
        path = Path(name)
        name = f"{path.stem} [{source.document_id}]{path.suffix}"
    taken.add(name.casefold())
    return name
