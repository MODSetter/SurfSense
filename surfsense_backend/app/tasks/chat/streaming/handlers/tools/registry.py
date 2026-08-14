"""Resolve completion-emission modules by tool name."""

from __future__ import annotations

import importlib
from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.connector.shared.tool_names import (
    SHARED_CONNECTOR_TOOLS,
)
from app.tasks.chat.streaming.handlers.tools.deliverables.tool_names import (
    DELIVERABLE_TOOLS,
)
from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)
from app.tasks.chat.streaming.handlers.tools.filesystem.tool_names import (
    FILESYSTEM_TOOLS,
)

_BASE = "app.tasks.chat.streaming.handlers.tools"
_CONNECTOR_SHARED = "connector.shared"

_EMISSION_ALIAS: dict[str, str] = {
    "edit_file": "filesystem.write_file",
    "execute_code": "filesystem.execute",
}


def _emission_module(tool_name: str) -> str:
    if tool_name in _EMISSION_ALIAS:
        return _EMISSION_ALIAS[tool_name]
    if tool_name in SHARED_CONNECTOR_TOOLS:
        return _CONNECTOR_SHARED
    if tool_name in DELIVERABLE_TOOLS:
        return f"deliverables.{tool_name}"
    if tool_name in FILESYSTEM_TOOLS:
        return f"filesystem.{tool_name}"
    return tool_name


def _import_emission(tool_name: str):
    try:
        return importlib.import_module(
            f"{_BASE}.{_emission_module(tool_name)}.emission"
        )
    except ModuleNotFoundError:
        return importlib.import_module(f"{_BASE}.default.emission")


def iter_tool_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    yield from _import_emission(ctx.tool_name).iter_completion_emission_frames(ctx)
