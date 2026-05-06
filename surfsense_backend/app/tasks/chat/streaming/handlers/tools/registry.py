"""Resolve thinking and emission modules by tool name."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

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
from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)

_BASE = "app.tasks.chat.streaming.handlers.tools"
_CONNECTOR_SHARED = "connector.shared"

_THINKING_ALIAS: dict[str, str] = {
    "execute_code": "filesystem.execute",
}
_EMISSION_ALIAS: dict[str, str] = {
    "edit_file": "filesystem.write_file",
    "execute_code": "filesystem.execute",
}


def _thinking_module(tool_name: str) -> str:
    if tool_name in SHARED_CONNECTOR_TOOLS:
        return _CONNECTOR_SHARED
    if tool_name in FILESYSTEM_TOOLS:
        return f"filesystem.{tool_name}"
    if tool_name in DELIVERABLE_TOOLS:
        return f"deliverables.{tool_name}"
    return _THINKING_ALIAS.get(tool_name, tool_name)


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


def _import_thinking(tool_name: str):
    try:
        return importlib.import_module(f"{_BASE}.{_thinking_module(tool_name)}.thinking")
    except ModuleNotFoundError:
        return importlib.import_module(f"{_BASE}.default.thinking")


def _import_emission(tool_name: str):
    try:
        return importlib.import_module(f"{_BASE}.{_emission_module(tool_name)}.emission")
    except ModuleNotFoundError:
        return importlib.import_module(f"{_BASE}.default.emission")


def resolve_tool_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    return _import_thinking(tool_name).resolve_start_thinking(tool_name, tool_input)


def resolve_tool_completed_thinking_step(
    tool_name: str, tool_output: Any, last_items: list[str]
) -> tuple[str, list[str]]:
    return _import_thinking(tool_name).resolve_completed_thinking(
        tool_name, tool_output, last_items
    )


def iter_tool_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    yield from _import_emission(ctx.tool_name).iter_completion_emission_frames(ctx)
