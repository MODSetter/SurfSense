"""``knowledge_base`` route: full and read-only ``SurfSenseSubagentSpec`` builders.

KB owns its destructive-FS approval ruleset (:data:`KB_RULESET`); rules
are layered into KB's :class:`PermissionMiddleware` (built inside
``build_kb_middleware``). One emitter, one wire format, one source of truth.
"""

from __future__ import annotations

from typing import Any, cast

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.subagents.shared.spec import SurfSenseSubagentSpec
from app.agents.shared.filesystem_selection import FilesystemMode
from app.agents.new_chat.permissions import Rule, Ruleset

from .middleware_stack import build_kb_middleware
from .prompts import load_description, load_readonly_system_prompt, load_system_prompt
from .tools.index import DESTRUCTIVE_FS_OPS

NAME = "knowledge_base"
READONLY_NAME = "knowledge_base_readonly"

KB_RULESET = Ruleset(
    origin=NAME,
    rules=[Rule(permission=op, pattern="*", action="ask") for op in DESTRUCTIVE_FS_OPS],
)

_KB_READONLY_RULESET = Ruleset(origin=READONLY_NAME, rules=[])


def build_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    mcp_tools: list[BaseTool] | None = None,
) -> SurfSenseSubagentSpec:
    del mcp_tools
    llm = model if model is not None else dependencies["llm"]
    filesystem_mode: FilesystemMode = dependencies["filesystem_mode"]
    spec = cast(
        SubAgent,
        {
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
                subagent_name=NAME,
                ruleset=KB_RULESET,
            ),
        },
    )
    return SurfSenseSubagentSpec(spec=spec, ruleset=KB_RULESET)


def build_readonly_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
) -> SurfSenseSubagentSpec:
    llm = model if model is not None else dependencies["llm"]
    filesystem_mode: FilesystemMode = dependencies["filesystem_mode"]
    spec = cast(
        SubAgent,
        {
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
                subagent_name=READONLY_NAME,
                ruleset=None,
            ),
        },
    )
    return SurfSenseSubagentSpec(spec=spec, ruleset=_KB_READONLY_RULESET)
