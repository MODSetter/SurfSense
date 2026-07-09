"""Central registry of route ``build_subagent`` callables (keyed by ``NAME``)."""

from __future__ import annotations

import time as _perf_time
from typing import Any, Protocol

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.constants import (
    SUBAGENT_TO_REQUIRED_CONNECTOR_MAP,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.agent import (
    build_subagent as build_deliverables_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.google_maps.agent import (
    build_subagent as build_google_maps_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.google_search.agent import (
    build_subagent as build_google_search_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.instagram.agent import (
    build_subagent as build_instagram_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.knowledge_base.agent import (
    build_subagent as build_knowledge_base_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.mcp_discovery.agent import (
    build_subagent as build_mcp_discovery_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.memory.agent import (
    build_subagent as build_memory_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.reddit.agent import (
    build_subagent as build_reddit_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.web_crawler.agent import (
    build_subagent as build_web_crawler_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.youtube.agent import (
    build_subagent as build_youtube_subagent,
)

# File connectors stay native — they enrich the knowledge base. Every other
# connector (Slack/Jira/Linear/ClickUp/Airtable/Notion/Confluence/Gmail/
# Calendar) migrated to hosted MCP under ``mcp_discovery``; Discord/Teams/Luma
# were deprecated (no viable official MCP server). Their old packages are gone.
from app.agents.chat.multi_agent_chat.subagents.connectors.dropbox.agent import (
    build_subagent as build_dropbox_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.connectors.google_drive.agent import (
    build_subagent as build_google_drive_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.connectors.onedrive.agent import (
    build_subagent as build_onedrive_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
)
from app.agents.chat.multi_agent_chat.subagents.shared.spec import SurfSenseSubagentSpec
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()


class SubagentBuilder(Protocol):
    def __call__(
        self,
        *,
        dependencies: dict[str, Any],
        model: BaseChatModel | None = None,
        middleware_stack: dict[str, Any] | None = None,
        mcp_tools: list[BaseTool] | None = None,
    ) -> SurfSenseSubagentSpec: ...


SUBAGENT_BUILDERS_BY_NAME: dict[str, SubagentBuilder] = {
    "deliverables": build_deliverables_subagent,
    "dropbox": build_dropbox_subagent,
    "google_drive": build_google_drive_subagent,
    "google_maps": build_google_maps_subagent,
    "google_search": build_google_search_subagent,
    "instagram": build_instagram_subagent,
    "knowledge_base": build_knowledge_base_subagent,
    "mcp_discovery": build_mcp_discovery_subagent,
    "memory": build_memory_subagent,
    "onedrive": build_onedrive_subagent,
    "reddit": build_reddit_subagent,
    "web_crawler": build_web_crawler_subagent,
    "youtube": build_youtube_subagent,
}


def _route_resource_package(builder: SubagentBuilder) -> str:
    mod = builder.__module__
    return mod[: -len(".agent")] if mod.endswith(".agent") else mod.rsplit(".", 1)[0]


def main_prompt_registry_subagent_lines(exclude: list[str]) -> list[tuple[str, str]]:
    """(name, description) for registry specialists included for **task** (same rules as ``build_subagents``)."""
    banned = frozenset(("memory",)) | frozenset(exclude)
    rows: list[tuple[str, str]] = []
    for name in sorted(SUBAGENT_BUILDERS_BY_NAME):
        if name in banned:
            continue
        builder = SUBAGENT_BUILDERS_BY_NAME[name]
        pkg = _route_resource_package(builder)
        blurb = read_md_file(pkg, "description").strip()
        if not blurb:
            blurb = name.replace("_", " ").title()
        rows.append((name, blurb))
    return rows


def get_subagents_to_exclude(
    available_connectors: list[str] | None,
) -> list[str]:
    if available_connectors is None:
        return []
    available_tokens = frozenset(available_connectors)
    excluded_names: set[str] = set()
    for builder_name in SUBAGENT_BUILDERS_BY_NAME:
        required_tokens = SUBAGENT_TO_REQUIRED_CONNECTOR_MAP.get(builder_name)
        if required_tokens is None:
            excluded_names.add(builder_name)
            continue
        if not required_tokens:
            continue
        if not (required_tokens & available_tokens):
            excluded_names.add(builder_name)
    return sorted(excluded_names)


def _filter_disabled_tools_in_place(
    spec: SubAgent,
    disabled_names: frozenset[str],
) -> None:
    """Drop UI-disabled tools from ``spec["tools"]``."""
    if not disabled_names:
        return
    tools = spec.get("tools")  # type: ignore[typeddict-item]
    if isinstance(tools, list):
        spec["tools"] = [  # type: ignore[typeddict-unknown-key]
            t for t in tools if getattr(t, "name", None) not in disabled_names
        ]


def _inject_ask_kb_tool_in_place(spec: SubAgent, ask_kb_tool: BaseTool) -> None:
    """Append ``ask_knowledge_base`` to every non-KB spec (skips a self-call)."""
    if spec["name"] == "knowledge_base":
        return
    tools = spec.get("tools")  # type: ignore[typeddict-item]
    if not isinstance(tools, list):
        spec["tools"] = [ask_kb_tool]  # type: ignore[typeddict-unknown-key]
        return
    if any(getattr(t, "name", None) == ask_kb_tool.name for t in tools):
        return
    tools.append(ask_kb_tool)


def build_subagents(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    mcp_tools_by_agent: dict[str, list[BaseTool]] | None = None,
    exclude: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    ask_kb_tool: BaseTool | None = None,
) -> list[SubAgent]:
    """Build registry subagents; skip memory; skip names in exclude."""
    mcp = mcp_tools_by_agent or {}
    specs: list[SubAgent] = []
    excluded = ["memory"]
    if exclude:
        excluded.extend(exclude)
    disabled_names = frozenset(disabled_tools or ())
    _timings: list[tuple[str, float]] = []
    for name in sorted(SUBAGENT_BUILDERS_BY_NAME):
        if name in excluded:
            continue
        builder = SUBAGENT_BUILDERS_BY_NAME[name]
        _t0 = _perf_time.perf_counter()
        result = builder(
            dependencies=dependencies,
            model=model,
            middleware_stack=middleware_stack,
            mcp_tools=mcp.get(name),
        )
        _timings.append((name, _perf_time.perf_counter() - _t0))
        spec = result.spec
        _filter_disabled_tools_in_place(spec, disabled_names)
        if ask_kb_tool is not None:
            _inject_ask_kb_tool_in_place(spec, ask_kb_tool)
        specs.append(spec)
    if _timings:
        _detail = " ".join(f"{n}={dt:.3f}s" for n, dt in _timings)
        _perf_log.info("[build_subagents.detail] %s", _detail)
    return specs
