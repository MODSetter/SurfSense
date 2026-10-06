"""A backstop for the edit rule: no file the agent made may pass for opencode's instructions.

The rule is case-insensitive only on Windows; a name it misses is renamed here.
"""

import os
from pathlib import Path

from modules.agent.thread_folder.mirror_path import INSTRUCTION_NAMES


def rename_instruction_files(outputs: Path) -> None:
    """Rename anything under `outputs/` named like an instruction file to `<name>_`."""
    if not outputs.is_dir():
        return
    for entry in list(os.scandir(outputs)):
        path = Path(entry.path)
        if entry.name.casefold() in INSTRUCTION_NAMES:
            target = path.with_name(f"{entry.name}_")
            while target.exists():
                target = target.with_name(f"{target.name}_")
            os.replace(path, target)
            path = target
        if entry.is_dir(follow_symlinks=False) and not entry.is_junction():
            rename_instruction_files(path)
