"""An analysis chart as a document script asks for it: by name, `analysis-<run>-<stem>`.

A plain file name, so the runner places it at IMAGES_DIR/<name>.png as it
places a source figure. The chart lives in its thread's outputs/analysis/.
"""

import re
import uuid
from pathlib import Path

from modules.agent.thread_folder.layout import OUTPUTS
from worker.document_script.kept_outputs import KEPT_STEM

ANALYSIS = "analysis"
CHART_SUFFIX = ".png"
_RUN = r"[0-9a-f]{8}"
_NAME = re.compile(rf"analysis-({_RUN})-({KEPT_STEM.pattern})")


def new_run() -> str:
    """A run's id: short, since the thread folder's paths count against Windows' 260."""
    return uuid.uuid4().hex[:8]


def run_folder(thread_folder: Path, run: str) -> Path:
    """Where one run's tables and charts are kept for the user and for later documents."""
    return thread_folder / OUTPUTS / ANALYSIS / run


def chart_name(run: str, file_name: str) -> str:
    """The name a kept PNG is placed by."""
    return f"analysis-{run}-{Path(file_name).stem}"


def is_chart_name(name: str) -> bool:
    return _NAME.fullmatch(name) is not None


def chart_file(thread_folder: Path, name: str) -> Path:
    """The PNG a chart name stands for in this thread's folder; LookupError when it has none."""
    match = _NAME.fullmatch(name)
    if match is None:
        raise LookupError(f"{name!r} is not a chart name")
    path = run_folder(thread_folder, match[1]) / f"{match[2]}{CHART_SUFFIX}"
    if path.is_symlink() or not path.is_file():
        raise LookupError(f"no chart {name} in this thread")
    return path
