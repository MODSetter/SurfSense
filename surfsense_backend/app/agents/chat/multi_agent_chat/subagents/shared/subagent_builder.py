"""Build delegated sub-agent specs from route-local pieces."""

from __future__ import annotations

import logging
import re
import time as _perf_time
from typing import Any, cast

from deepagents import SubAgent
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import (
    Ruleset,
    build_permission_mw,
)
from app.agents.chat.multi_agent_chat.subagents.shared.md_file_reader import (
    read_shared_snippet,
)
from app.agents.chat.multi_agent_chat.subagents.shared.spec import (
    SURF_CONTEXT_HINT_PROVIDER_KEY,
    ContextHintProvider,
    SurfSenseSubagentSpec,
)
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()

# ``<include snippet="NAME"/>`` directive. Matches an XML-style self-closing
# tag whose ``snippet`` attribute names a file in ``shared/snippets/``.
# Whitespace around the attribute and self-close is tolerated; the snippet
# name itself must be a bare identifier (letters / digits / underscores) so
# we never pull a path-traversal value into ``read_shared_snippet``.
_INCLUDE_DIRECTIVE_RE = re.compile(
    r"<include\s+snippet=\"(?P<name>[A-Za-z0-9_]+)\"\s*/>"
)


def _resolve_includes(prompt: str, *, subagent_name: str) -> str:
    """Replace ``<include snippet="X"/>`` directives with the snippet body.

    Unknown snippet names raise; an empty body is treated as unknown so a
    typo or missing file fails loudly at startup instead of silently
    shipping a broken prompt to the LLM.
    """

    def _replace(match: re.Match[str]) -> str:
        name = match.group("name")
        body = read_shared_snippet(name)
        if not body.strip():
            raise ValueError(
                f"Subagent {subagent_name!r}: unknown or empty shared "
                f"snippet {name!r} referenced via <include>."
            )
        return body

    return _INCLUDE_DIRECTIVE_RE.sub(_replace, prompt)


def _user_allowlist_for(
    dependencies: dict[str, Any], subagent_name: str
) -> Ruleset | None:
    """Return the user's persisted allow-rules for ``subagent_name`` if any.

    Populated by the agent factory from
    :func:`app.services.user_tool_allowlist.fetch_user_allowlist_rulesets`.
    Returning ``None`` is the common case (fresh accounts, non-MCP
    subagents, or no "Always Allow" interactions yet).
    """
    by_subagent = dependencies.get("user_allowlist_by_subagent") or {}
    user_allowlist = by_subagent.get(subagent_name)
    if isinstance(user_allowlist, Ruleset) and user_allowlist.rules:
        return user_allowlist
    return None


def pack_subagent(
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: list[BaseTool],
    ruleset: Ruleset,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    context_hint_provider: ContextHintProvider | None = None,
) -> SurfSenseSubagentSpec:
    """Pack the route-local pieces into one sub-agent spec + its Ruleset.

    Tool gating is uniformly performed by a per-subagent
    :class:`PermissionMiddleware`. Three rule layers are evaluated
    earliest-to-latest (last match wins):

    1. SurfSense defaults — single ``allow */*`` rule (added by
       :func:`build_permission_mw`).
    2. ``ruleset`` — the subagent's coded approval rules (e.g. KB's
       destructive-FS ``ask`` rules, connector ``ask`` writes).
    3. The user's persisted allow-list for this subagent — pulled from
       ``dependencies['user_allowlist_by_subagent'][name]``. User
       ``allow`` rules layered last override coded ``ask`` rules,
       implementing the "Always Allow" UX without re-asking on the
       next turn.

    The shared ``permission`` slot from ``middleware_stack`` is dropped
    so each subagent owns its own rule surface and cannot accidentally
    share state with the main agent's permission middleware.
    """
    if not system_prompt.strip():
        msg = f"Subagent {name!r}: system_prompt is empty"
        raise ValueError(msg)

    _t0 = _perf_time.perf_counter()
    system_prompt = _resolve_includes(system_prompt, subagent_name=name)
    _t_resolve = _perf_time.perf_counter() - _t0

    flags = dependencies["flags"]
    user_allowlist = _user_allowlist_for(dependencies, name)
    subagent_rulesets: list[Ruleset] = [ruleset]
    if user_allowlist is not None:
        subagent_rulesets.append(user_allowlist)
    _t0 = _perf_time.perf_counter()
    per_subagent_perm = build_permission_mw(
        flags=flags,
        subagent_rulesets=subagent_rulesets,
        tools=tools,
        trusted_tool_saver=dependencies.get("trusted_tool_saver"),
    )
    _t_perm = _perf_time.perf_counter() - _t0
    _perf_log.info(
        "[pack_subagent] name=%s tools=%d resolve_includes=%.3fs "
        "build_permission_mw=%.3fs",
        name,
        len(tools),
        _t_resolve,
        _t_perm,
    )

    prepended: list[Any] = []
    for slot, mw in (middleware_stack or {}).items():
        if mw is None:
            continue
        if slot == "permission":
            continue
        prepended.append(mw)
    if per_subagent_perm is not None:
        prepended.append(per_subagent_perm)
    middleware: list[Any] = [*prepended, PatchToolCallsMiddleware()]
    spec_dict: dict[str, Any] = {
        "name": name,
        "description": description,
        "system_prompt": system_prompt,
        "tools": tools,
        "middleware": middleware,
    }
    if model is not None:
        spec_dict["model"] = model
    if context_hint_provider is not None:
        # Stash the callback on the dict so it survives the trip through
        # registry / middleware unpacking (both treat the spec as opaque).
        spec_dict[SURF_CONTEXT_HINT_PROVIDER_KEY] = context_hint_provider
    return SurfSenseSubagentSpec(
        spec=cast(SubAgent, spec_dict),
        ruleset=ruleset,
        context_hint_provider=context_hint_provider,
    )
