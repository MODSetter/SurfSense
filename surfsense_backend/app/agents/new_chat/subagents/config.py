"""Builders for specialized SurfSense subagents.

Each subagent is built from three pieces:

1. A name + description + system prompt (the user-facing contract for
   when ``task`` should delegate to this role).
2. A filtered tool list (subset of the parent's bound tools).
3. A :class:`PermissionMiddleware` instance carrying a deny ruleset that
   prevents the subagent from acting outside its scope (e.g. an
   explore-only role cannot mutate state).

Skill sources (``/skills/builtin/`` + ``/skills/space/``) are inherited
from the parent unconditionally — every subagent benefits from the same
authored guidance documents.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from app.agents.new_chat.middleware.skills_backends import default_skills_sources
from app.agents.new_chat.permissions import Rule, Ruleset

if TYPE_CHECKING:
    from deepagents import SubAgent
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool name constants
# ---------------------------------------------------------------------------

# Read-only tools that ``explore`` is permitted to use. Names match the
# tools provided by the deepagents ``FilesystemMiddleware`` (``ls``, ``read_file``,
# ``glob``, ``grep``) plus the SurfSense-side read tools.
EXPLORE_READ_TOOLS: frozenset[str] = frozenset(
    {
        "search_surfsense_docs",
        "web_search",
        "scrape_webpage",
        "read_file",
        "ls",
        "glob",
        "grep",
    }
)

# Tools ``report_writer`` may call. The set is intentionally narrow so the
# subagent doesn't drift into tangential research; if richer source-gathering
# is needed, the parent should hand off to ``explore`` first.
REPORT_WRITER_TOOLS: frozenset[str] = frozenset(
    {
        "search_surfsense_docs",
        "read_file",
        "generate_report",
    }
)

# Wildcard patterns that match write tools we deny by default in read-only
# subagents. Anchored at start AND end via :func:`Rule` semantics. We use
# substring-style ``*verb*`` patterns because connector tool names typically
# put the verb in the middle (``linear_create_issue``, ``slack_send_message``,
# ``notion_update_page``); strict suffix patterns (``*_create``) miss those.
#
# A handful of canonical exact-match names is appended so that bare verbs
# (``edit``, ``write``) are also blocked even when a connector dropped the
# usual prefix.
WRITE_TOOL_DENY_PATTERNS: tuple[str, ...] = (
    "*create*",
    "*update*",
    "*delete*",
    "*send*",
    "*write*",
    "*edit*",
    "*move*",
    "*mkdir*",
    "*upload*",
    "edit_file",
    "write_file",
    "move_file",
    "mkdir",
    "update_memory",
    "update_memory_team",
    "update_memory_private",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Tool names that are NOT in the registry's ``tools`` list because they
# are provided dynamically by middleware at compile time. We don't pass
# them through ``_filter_tools`` (the actual ``BaseTool`` instances live
# inside the middleware), but we do exempt them from the "missing" warning
# below — operators were seeing spurious noise like
# ``missing: ['glob', 'grep', 'ls', 'read_file']`` even though those
# tools are reachable via :class:`SurfSenseFilesystemMiddleware` once the
# subagent is compiled.
_MIDDLEWARE_PROVIDED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "glob",
        "grep",
        "execute",
        "write_todos",
        "task",
    }
)


def _filter_tools(
    tools: Sequence[BaseTool],
    allowed_names: Iterable[str],
) -> list[BaseTool]:
    """Return only tools whose ``name`` appears in ``allowed_names``.

    Tools are looked up by exact name. Names matching
    :data:`_MIDDLEWARE_PROVIDED_TOOL_NAMES` are intentionally absent from
    ``tools`` (they're injected by middleware at compile time) and are
    silently excluded from the "missing" warning so operators don't see
    false positives every build.
    """
    allowed = set(allowed_names)
    selected = [t for t in tools if t.name in allowed]
    missing = sorted(
        (allowed - {t.name for t in selected}) - _MIDDLEWARE_PROVIDED_TOOL_NAMES
    )
    if missing:
        logger.info(
            "Subagent build: %d/%d registry tools available; missing: %s",
            len(selected),
            len(allowed - _MIDDLEWARE_PROVIDED_TOOL_NAMES),
            missing,
        )
    return selected


def _read_only_deny_rules() -> list[Rule]:
    """Synthesize a list of deny rules covering common write-tool patterns."""
    return [
        Rule(permission=pattern, pattern="*", action="deny")
        for pattern in WRITE_TOOL_DENY_PATTERNS
    ]


def _build_permission_middleware(deny_rules: list[Rule], origin: str):
    """Construct a :class:`PermissionMiddleware` seeded with ``deny_rules``.

    Imported lazily because the middleware module pulls in interrupt/HITL
    machinery we don't want at import time of this config file.
    """
    from app.agents.new_chat.middleware.permission import PermissionMiddleware

    return PermissionMiddleware(
        rulesets=[Ruleset(rules=deny_rules, origin=origin)],
    )


def _wrap_with_subagent_essentials(
    custom_middleware: list,
    *,
    agent_tools: Sequence[BaseTool],
    extra_middleware: Sequence[Any] | None = None,
):
    """Compose the final middleware list for a specialized subagent.

    Order, outer to inner:

    1. ``extra_middleware`` — provided by the caller (typically the parent
       agent's ``SurfSenseFilesystemMiddleware`` and ``TodoListMiddleware``)
       so the subagent inherits the parent's filesystem/todo view. These
       run **before** the subagent-local middleware so their tools are
       wired up before permissioning kicks in.
    2. ``custom_middleware`` — subagent-local rules (e.g. permission deny
       lists).
    3. :class:`PatchToolCallsMiddleware` — normalizes tool-call shapes.
    4. :class:`DedupHITLToolCallsMiddleware` — collapses duplicate HITL
       calls using metadata declared at registry time.

    Without ``extra_middleware`` the subagent will only have the registry
    tools listed in its ``tools`` field — meaning ``read_file``, ``ls``,
    ``grep``, etc. won't exist. Always pass ``extra_middleware`` from the
    parent unless you specifically want a sandboxed subagent.
    """
    from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware

    from app.agents.new_chat.middleware import DedupHITLToolCallsMiddleware

    return [
        *(extra_middleware or []),
        *custom_middleware,
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(agent_tools=list(agent_tools)),
    ]


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

EXPLORE_SYSTEM_PROMPT = """You are the **explore** subagent for SurfSense.

## Your job
Conduct read-only research across the user's knowledge base, the web, and any documents the parent agent has surfaced. Return a synthesized answer with explicit citations — never speculate beyond the sources you have actually inspected.

## Tools available
- `search_surfsense_docs` — fast hybrid search over the user's knowledge base.
- `web_search` — only when the user's KB clearly does not contain the answer.
- `scrape_webpage` — to read a URL the user or the search results provided.
- `read_file`, `ls`, `glob`, `grep` — to inspect specific documents or trees the parent has flagged.

## Rules
- Read-only. You cannot create, edit, delete, send, or move anything.
- Cite every claim. Use `[citation:chunk_id]` exactly as the chunk tag specifies.
- If a sub-question has no support in the inspected sources, say so explicitly. Do not fabricate.
- Return the most useful synthesis in your single final message. The parent agent will not be able to follow up.
"""


REPORT_WRITER_SYSTEM_PROMPT = """You are the **report_writer** subagent for SurfSense.

## Your job
Produce a single high-quality report deliverable using `generate_report`. The parent has already gathered (or knows where to gather) the underlying sources.

## Workflow
1. **Outline first.** Before calling `generate_report`, write a one-paragraph outline of the sections you plan to produce. Confirm the outline reflects the parent's instructions.
2. **Source resolution.** Decide whether to call `search_surfsense_docs` and `read_file` for any final-checks, or whether the parent's earlier tool calls already cover the source set.
3. **One report.** Call `generate_report` exactly once with `source_strategy` chosen per the topic and chat history (see the `report-writing` skill).
4. **Confirm.** End with a one-sentence summary in your final message — never paste the report back into chat; the artifact card renders itself.
"""


CONNECTOR_NEGOTIATOR_SYSTEM_PROMPT = """You are the **connector_negotiator** subagent for SurfSense.

## Your job
Coordinate cross-connector workflows: chains where the result of one service's tool feeds into another's. Common shapes include "find Linear issues mentioned in last week's Slack messages", "draft a Gmail reply citing a Notion doc", or "list Linear tickets opened by the same person who filed Jira FOO-123".

## Workflow
1. **Plan.** Identify the connector hops needed and the order they should run in. Write a short plan in your first message.
2. **Verify access.** Use `get_connected_accounts` to confirm the relevant connectors are actually wired up before issuing tool calls. If a connector is missing, stop and report — do not fabricate.
3. **Execute.** Run each hop, citing IDs (issue keys, message ts, page IDs) in your scratch notes so the parent can audit.
4. **Hand back.** Return a structured summary with the final answer plus the chain of evidence (issue → message → page, etc.).

## Caveats
- If a hop fails, do not retry blindly — return the partial result and explain.
- Mutating tools (create, update, delete, send) require parent permission; you are NOT cleared to call them on your own.
"""


# ---------------------------------------------------------------------------
# Subagent builders
# ---------------------------------------------------------------------------


def build_explore_subagent(
    *,
    tools: Sequence[BaseTool],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
) -> SubAgent:
    """Build the read-only ``explore`` subagent spec.

    Pass ``extra_middleware`` (typically the parent's filesystem + todo
    middleware) so the subagent can actually use ``read_file``, ``ls``,
    ``grep``, ``glob`` — which its system prompt promises but which only
    exist when their middleware is mounted.
    """
    from deepagents import SubAgent  # noqa: F401  (TypedDict for type clarity)

    selected_tools = _filter_tools(tools, EXPLORE_READ_TOOLS)
    deny_rules = _read_only_deny_rules()
    permission_mw = _build_permission_middleware(deny_rules, origin="subagent_explore")

    spec: dict = {
        "name": "explore",
        "description": (
            "Read-only research across the user's knowledge base and the web. "
            "Use when the parent needs deeply-cited synthesis without "
            "modifying anything."
        ),
        "system_prompt": EXPLORE_SYSTEM_PROMPT,
        "tools": selected_tools,
        "middleware": _wrap_with_subagent_essentials(
            [permission_mw],
            agent_tools=selected_tools,
            extra_middleware=extra_middleware,
        ),
        "skills": default_skills_sources(),
    }
    if model is not None:
        spec["model"] = model
    return spec  # type: ignore[return-value]


def build_report_writer_subagent(
    *,
    tools: Sequence[BaseTool],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
) -> SubAgent:
    """Build the ``report_writer`` subagent spec.

    Read-only deny ruleset still applies — the subagent should call
    ``generate_report`` and nothing else mutating. ``generate_report``
    creates a report artifact via a backend service and is intentionally
    **not** denied.

    Pass ``extra_middleware`` (typically the parent's filesystem + todo
    middleware) so the subagent can run ``read_file`` for source-checks
    before calling ``generate_report``.
    """
    selected_tools = _filter_tools(tools, REPORT_WRITER_TOOLS)
    deny_rules = _read_only_deny_rules()
    permission_mw = _build_permission_middleware(
        deny_rules, origin="subagent_report_writer"
    )

    spec: dict = {
        "name": "report_writer",
        "description": (
            "Produce a single Markdown report artifact via generate_report, "
            "using the outline-then-fill protocol. Use when the parent has "
            "decided a deliverable is needed."
        ),
        "system_prompt": REPORT_WRITER_SYSTEM_PROMPT,
        "tools": selected_tools,
        "middleware": _wrap_with_subagent_essentials(
            [permission_mw],
            agent_tools=selected_tools,
            extra_middleware=extra_middleware,
        ),
        "skills": default_skills_sources(),
    }
    if model is not None:
        spec["model"] = model
    return spec  # type: ignore[return-value]


def build_connector_negotiator_subagent(
    *,
    tools: Sequence[BaseTool],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
) -> SubAgent:
    """Build the ``connector_negotiator`` subagent spec.

    Inherits all MCP / connector tools the parent has plus
    ``get_connected_accounts``. Read-only by default; permission rules deny
    write/mutation patterns. The parent agent re-asks for permission if a
    connector mutation is genuinely needed.

    Pass ``extra_middleware`` (typically the parent's filesystem + todo
    middleware) so this subagent shares the parent's filesystem view when
    citing evidence across hops.
    """
    parent_tool_names = {t.name for t in tools}
    allowed: set[str] = set()
    if "get_connected_accounts" in parent_tool_names:
        allowed.add("get_connected_accounts")
    # Inherit anything that smells connector- or MCP-related but is not a
    # bulk-write API. Heuristic: keep all parent tools; rely on the deny
    # ruleset to block mutation patterns. This mirrors the plan: "all
    # MCP/connector tools the parent has".
    for name in parent_tool_names:
        allowed.add(name)
    selected_tools = _filter_tools(tools, allowed)

    deny_rules = _read_only_deny_rules()
    permission_mw = _build_permission_middleware(
        deny_rules, origin="subagent_connector_negotiator"
    )

    spec: dict = {
        "name": "connector_negotiator",
        "description": (
            "Coordinate read-only chains across connectors (Slack → Linear, "
            "Notion → Gmail, etc.). Returns a structured summary with the "
            "evidence chain. Cannot mutate connector state."
        ),
        "system_prompt": CONNECTOR_NEGOTIATOR_SYSTEM_PROMPT,
        "tools": selected_tools,
        "middleware": _wrap_with_subagent_essentials(
            [permission_mw],
            agent_tools=selected_tools,
            extra_middleware=extra_middleware,
        ),
        "skills": default_skills_sources(),
    }
    if model is not None:
        spec["model"] = model
    return spec  # type: ignore[return-value]


def build_specialized_subagents(
    *,
    tools: Sequence[BaseTool],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
) -> list[SubAgent]:
    """Return the canonical list of specialized subagents to register.

    Order matters only for the order they appear in the ``task`` tool
    description — most useful first.
    """
    return [
        build_explore_subagent(
            tools=tools, model=model, extra_middleware=extra_middleware
        ),
        build_report_writer_subagent(
            tools=tools, model=model, extra_middleware=extra_middleware
        ),
        build_connector_negotiator_subagent(
            tools=tools, model=model, extra_middleware=extra_middleware
        ),
    ]
