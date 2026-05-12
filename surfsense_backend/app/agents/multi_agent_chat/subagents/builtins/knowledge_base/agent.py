"""`knowledge_base` route: ``SubAgent`` spec for the SurfSense KB specialist.

Owns the ``/documents/`` workspace (read, write, edit, search, organise)
and shares the orchestrator's ``workspace_tree_text`` and ``kb_priority``
via state. KB conforms to :class:`SubagentBuilder` but composes its
middleware list itself: it picks individual entries from
``middleware_stack`` by key so resilience lands just outside the
Anthropic cache (inside the filesystem and projection middlewares),
which a flat prepend can't satisfy.
"""

from __future__ import annotations

from typing import Any, cast

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from app.agents.multi_agent_chat.middleware.shared.anthropic_cache import (
    build_anthropic_cache_mw,
)
from app.agents.multi_agent_chat.middleware.shared.compaction import (
    build_compaction_mw,
)
from app.agents.multi_agent_chat.middleware.shared.filesystem import (
    build_filesystem_mw,
)
from app.agents.multi_agent_chat.middleware.shared.kb_context_projection import (
    build_kb_context_projection_mw,
)
from app.agents.multi_agent_chat.middleware.shared.patch_tool_calls import (
    build_patch_tool_calls_mw,
)
from app.agents.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
)
from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)
from app.agents.new_chat.filesystem_selection import FilesystemMode

from .tools.index import destructive_fs_interrupt_on

NAME = "knowledge_base"


def build_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    extra_tools_bucket: ToolsPermissions | None = None,  # noqa: ARG001 — KB ships fixed tools
) -> SubAgent:
    """Conforms to :class:`SubagentBuilder`; KB splices the shared stack itself."""
    llm = model if model is not None else dependencies["llm"]
    filesystem_mode: FilesystemMode = dependencies["filesystem_mode"]
    mws = middleware_stack or {}

    description = read_md_file(__package__, "description").strip() or (
        "Handles knowledge-base reads, writes, edits, and organisation."
    )
    prompt_stem = (
        "system_prompt_cloud"
        if filesystem_mode == FilesystemMode.CLOUD
        else "system_prompt_desktop"
    )
    system_prompt = read_md_file(__package__, prompt_stem).strip()

    resilience_mws = [
        m
        for m in (
            mws.get("retry"),
            mws.get("fallback"),
            mws.get("model_call_limit"),
            mws.get("tool_call_limit"),
        )
        if m is not None
    ]

    middleware: list[Any] = [
        mws["todos"],
        build_kb_context_projection_mw(),
        build_filesystem_mw(
            backend_resolver=dependencies["backend_resolver"],
            filesystem_mode=filesystem_mode,
            search_space_id=dependencies["search_space_id"],
            user_id=dependencies.get("user_id"),
            thread_id=dependencies.get("thread_id"),
        ),
        build_compaction_mw(llm),
        build_patch_tool_calls_mw(),
        *resilience_mws,
        build_anthropic_cache_mw(),
    ]

    spec: dict[str, Any] = {
        "name": NAME,
        "description": description,
        "system_prompt": system_prompt,
        "model": llm,
        "tools": [], # KB virtual FS tools are injected at runtime by SurfSenseFilesystemMiddleware
        "middleware": middleware,
        "interrupt_on": destructive_fs_interrupt_on(),
    }
    return cast(SubAgent, spec)
