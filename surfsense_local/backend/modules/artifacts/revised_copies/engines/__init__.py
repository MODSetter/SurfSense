"""The engines that edit a copy of the user's file, one per format: pure functions over files.

Imported on use, so each format loads only its own engine.
"""

import importlib
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modules.artifacts.revised_copies.engines.report import Report

_ENGINES = {"docx": "word", "xlsx": "excel", "pptx": "powerpoint"}


def engine_for(format: str) -> ModuleType:
    """The engine module for an artifact format: `apply`, and for Word its accept, reject and counts."""
    return importlib.import_module(f"{__name__}.{_ENGINES[format]}")


def apply_operations(
    format: str, original: Path, operations: list[dict[str, Any]], out: Path
) -> "Report":
    """All or nothing: one refused operation saves nothing (03, the apply report)."""
    return engine_for(format).apply(original, operations, out, partial=False)
