"""Compile the supervisor agent graph (supervisor prompt + caller-supplied routing tools)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import app.agents.multi_agent_chat.supervisor as supervisor_pkg

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from app.agents.multi_agent_chat.core.prompts import read_prompt_md

_BUILTIN_SPECIALISTS: frozenset[str] = frozenset({"research", "memory", "deliverables"})
_SPECIALIST_CAPABILITIES: dict[str, str] = {
    "research": "external research: web lookup, source gathering, and SurfSense documentation help.",
    "memory": "save durable long-lived memory items.",
    "deliverables": "final artifact generation: report, podcast, video presentation, resume, or image.",
    "gmail": "email inbox actions: search/read emails, draft updates, send messages, and trash emails.",
    "calendar": "scheduling actions: check availability, inspect events, create events, and update events.",
    "google_drive": "Drive file/document actions: locate files, inspect content, and manage files/folders.",
    "notion": "Notion page actions: create pages, update content, and delete pages.",
    "confluence": "Confluence page actions: find/read pages and create/update pages.",
    "dropbox": "Dropbox file storage actions: browse folders, read files, and manage file content.",
    "onedrive": "OneDrive file storage actions: browse folders, read files, and manage file content.",
    "discord": "Discord communication actions: read channels/threads and post replies.",
    "teams": "Microsoft Teams communication actions: read channels/threads and post replies.",
    "luma": "Luma event actions: list events, inspect event details, and create events.",
    "linear": "Linear workflow actions: search/update issues and inspect projects/cycles.",
    "jira": "Jira workflow actions: search/update issues and manage workflow transitions.",
    "clickup": "ClickUp workflow actions: find/update tasks and lists.",
    "airtable": "Airtable data actions: locate bases/tables and create/read/update records.",
    "slack": "Slack communication actions: read channel/thread history and post replies.",
    # generic_mcp specialist intentionally disabled for now.
    # "generic_mcp": "handle tasks through user-defined custom app integration tools not covered above.",
}
_SPECIALIST_ORDER: tuple[str, ...] = tuple(_SPECIALIST_CAPABILITIES.keys())


def _memory_capability_for_visibility(thread_visibility: Any | None) -> str:
    vis = str(getattr(thread_visibility, "value", thread_visibility)).upper()
    if vis == "SEARCH_SPACE":
        return "team memory actions: save shared team preferences, conventions, and long-lived team facts."
    return "user memory actions: save personal preferences, instructions, and long-lived user facts."


def _render_available_specialists_list(
    tools: Sequence[BaseTool],
    *,
    thread_visibility: Any | None,
) -> str:
    available_names = {
        tool.name for tool in tools if isinstance(getattr(tool, "name", None), str)
    }
    capabilities = dict(_SPECIALIST_CAPABILITIES)
    capabilities["memory"] = _memory_capability_for_visibility(thread_visibility)
    lines: list[str] = []
    for name in _SPECIALIST_ORDER:
        if name in _BUILTIN_SPECIALISTS or name in available_names:
            capability = capabilities[name]
            lines.append(f"- {name}: {capability}")
    return "\n".join(lines)


def _render_supervisor_prompt(
    template: str,
    tools: Sequence[BaseTool],
    *,
    thread_visibility: Any | None,
) -> str:
    specialist_list = _render_available_specialists_list(
        tools, thread_visibility=thread_visibility
    )
    return template.replace("{{AVAILABLE_SPECIALISTS_LIST}}", specialist_list)


def build_supervisor_agent(
    llm: BaseChatModel,
    *,
    tools: Sequence[BaseTool],
    checkpointer: Checkpointer | None = None,
    thread_visibility: Any | None = None,
    middleware: Sequence[Any] | None = None,
    context_schema: Any | None = None,
):
    """Compile the supervisor **agent** (graph). ``tools`` = output of ``build_supervisor_routing_tools``."""
    template = read_prompt_md(supervisor_pkg.__name__, "supervisor_prompt")
    system_prompt = _render_supervisor_prompt(
        template,
        tools,
        thread_visibility=thread_visibility,
    )
    kwargs: dict[str, Any] = {
        "system_prompt": system_prompt,
        "tools": list(tools),
        "checkpointer": checkpointer,
    }
    if middleware is not None:
        kwargs["middleware"] = list(middleware)
    if context_schema is not None:
        kwargs["context_schema"] = context_schema
    agent = create_agent(llm, **kwargs)
    if middleware is not None or context_schema is not None:
        return agent.with_config(
            {
                "recursion_limit": 10_000,
                "metadata": {"ls_integration": "multi_agent_supervisor"},
            }
        )
    return agent
