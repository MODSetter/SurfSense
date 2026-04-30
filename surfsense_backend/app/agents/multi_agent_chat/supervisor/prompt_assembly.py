"""Supervisor system prompt: template load, shared agent-identity injection, specialist list."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from langchain_core.tools import BaseTool

import app.agents.multi_agent_chat.supervisor as supervisor_pkg
from app.agents.multi_agent_chat.core.prompts import read_prompt_md
from app.agents.new_chat.prompts.composer import _build_citation_block, _read_fragment
from app.db import ChatVisibility

_MEMORY_SPECIALIST_PHRASE = "invoke the **memory** specialist"

_BUILTIN_SPECIALISTS: frozenset[str] = frozenset({"research", "memory", "deliverables"})
_SPECIALIST_CAPABILITIES: dict[str, str] = {
    "research": "external research: web lookup, source gathering, and SurfSense documentation help.",
    "memory": "save durable long-lived memory items.",
    "deliverables": "deliverables and shareable artifacts: reports, podcasts, video presentations, resumes, and images.",
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


def _normalize_chat_visibility(thread_visibility: Any | None) -> ChatVisibility:
    if thread_visibility is None:
        return ChatVisibility.PRIVATE
    if thread_visibility == ChatVisibility.SEARCH_SPACE:
        return ChatVisibility.SEARCH_SPACE
    raw = getattr(thread_visibility, "value", thread_visibility)
    if str(raw).upper() == "SEARCH_SPACE":
        return ChatVisibility.SEARCH_SPACE
    return ChatVisibility.PRIVATE


def _identity_fragment_key(thread_visibility: Any | None) -> str:
    """``private`` / ``team`` suffix for ``agent_*`` and ``memory_protocol_*`` fragments."""
    return (
        "team"
        if _normalize_chat_visibility(thread_visibility) == ChatVisibility.SEARCH_SPACE
        else "private"
    )


def _compose_identity_memory_citations(
    *,
    thread_visibility: Any | None,
    citations_enabled: bool,
) -> str:
    """Main-chat identity, memory protocol, and citation fragments (supervisor slice only)."""
    key = _identity_fragment_key(thread_visibility)
    today = datetime.now(UTC).date().isoformat()

    intro = _read_fragment(f"base/agent_{key}.md")
    if intro:
        intro = intro.format(resolved_today=today)

    memory = _read_fragment(f"base/memory_protocol_{key}.md").replace(
        "call update_memory",
        _MEMORY_SPECIALIST_PHRASE,
    )
    tail = (
        f"<system_instruction>\n{memory}\n\n</system_instruction>\n"
        + _build_citation_block(citations_enabled)
    )
    return "\n\n".join(part for part in (intro.strip(), tail.strip()) if part)


def _memory_specialist_capability(thread_visibility: Any | None) -> str:
    vis = str(getattr(thread_visibility, "value", thread_visibility)).upper()
    if vis == "SEARCH_SPACE":
        return "team memory actions: save shared team preferences, conventions, and long-lived team facts."
    return "user memory actions: save personal preferences, instructions, and long-lived user facts."


def _specialists_markdown(
    tools: Sequence[BaseTool],
    *,
    thread_visibility: Any | None,
) -> str:
    available_names = {
        tool.name for tool in tools if isinstance(getattr(tool, "name", None), str)
    }
    capabilities = dict(_SPECIALIST_CAPABILITIES)
    capabilities["memory"] = _memory_specialist_capability(thread_visibility)
    lines: list[str] = []
    for name in _SPECIALIST_ORDER:
        if name in _BUILTIN_SPECIALISTS or name in available_names:
            lines.append(f"- {name}: {capabilities[name]}")
    return "\n".join(lines)


def build_supervisor_system_prompt(
    tools: Sequence[BaseTool],
    *,
    thread_visibility: Any | None,
    citations_enabled: bool,
) -> str:
    """Load ``supervisor_prompt.md`` and fill placeholders."""
    template = read_prompt_md(supervisor_pkg.__name__, "supervisor_prompt")
    specialists = _specialists_markdown(tools, thread_visibility=thread_visibility)
    injected = _compose_identity_memory_citations(
        thread_visibility=thread_visibility,
        citations_enabled=citations_enabled,
    )
    return template.replace("{{AVAILABLE_SPECIALISTS_LIST}}", specialists).replace(
        "{{SUPERVISOR_BASE_INJECTION}}",
        injected,
    )
