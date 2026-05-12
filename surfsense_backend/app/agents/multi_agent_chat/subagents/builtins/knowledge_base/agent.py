"""`knowledge_base` route: full and read-only ``SubAgent`` specs."""

from __future__ import annotations

from typing import Any, cast

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from app.agents.multi_agent_chat.subagents.shared.permissions import ToolsPermissions
from app.agents.new_chat.filesystem_selection import FilesystemMode

from .middleware_stack import build_kb_middleware
from .prompts import load_description, load_readonly_system_prompt, load_system_prompt
from .tools.index import destructive_fs_interrupt_on

NAME = "knowledge_base"
READONLY_NAME = "knowledge_base_readonly"


def build_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    extra_tools_bucket: ToolsPermissions | None = None,  # noqa: ARG001 — KB ships fixed tools
) -> SubAgent:
    llm = model if model is not None else dependencies["llm"]
    filesystem_mode: FilesystemMode = dependencies["filesystem_mode"]
    spec: dict[str, Any] = {
        "name": NAME,
        "description": load_description(),
        "system_prompt": load_system_prompt(filesystem_mode),
        "model": llm,
        "tools": [],
        "middleware": build_kb_middleware(
            llm=llm,
            dependencies=dependencies,
            middleware_stack=middleware_stack,
            read_only=False,
        ),
        "interrupt_on": destructive_fs_interrupt_on(),
    }
    return cast(SubAgent, spec)


def build_readonly_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
) -> SubAgent:
    llm = model if model is not None else dependencies["llm"]
    filesystem_mode: FilesystemMode = dependencies["filesystem_mode"]
    spec: dict[str, Any] = {
        "name": READONLY_NAME,
        "description": "Read-only knowledge_base specialist (invoked via ask_knowledge_base).",
        "system_prompt": load_readonly_system_prompt(filesystem_mode),
        "model": llm,
        "tools": [],
        "middleware": build_kb_middleware(
            llm=llm,
            dependencies=dependencies,
            middleware_stack=middleware_stack,
            read_only=True,
        ),
        "interrupt_on": {},
    }
    return cast(SubAgent, spec)
