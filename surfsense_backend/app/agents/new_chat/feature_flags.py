"""
Feature flags for the SurfSense new_chat agent stack.

These flags gate the newer agent middleware (some ported from OpenCode,
some sourced from ``langchain.agents.middleware`` / ``deepagents``, some
SurfSense-native). Most shipped agent-stack upgrades default ON so Docker
image updates work even when older installs do not have newly introduced
environment variables. Risky/experimental integrations stay default OFF,
and the master kill-switch can still disable everything new.

All new middleware checks its flag at agent build time. If the master
kill-switch ``SURFSENSE_DISABLE_NEW_AGENT_STACK`` is set, every new
middleware is disabled regardless of its individual flag. This gives
operators a single switch to revert to pre-port behavior.

Examples
--------

Defaults:

    SURFSENSE_ENABLE_CONTEXT_EDITING=true
    SURFSENSE_ENABLE_COMPACTION_V2=true
    SURFSENSE_ENABLE_RETRY_AFTER=true
    SURFSENSE_ENABLE_MODEL_FALLBACK=false
    SURFSENSE_ENABLE_MODEL_CALL_LIMIT=true
    SURFSENSE_ENABLE_TOOL_CALL_LIMIT=true
    SURFSENSE_ENABLE_TOOL_CALL_REPAIR=true
    SURFSENSE_ENABLE_PERMISSION=true
    SURFSENSE_ENABLE_DOOM_LOOP=true
    SURFSENSE_ENABLE_LLM_TOOL_SELECTOR=false  # adds a per-turn LLM call
    SURFSENSE_ENABLE_STREAM_PARITY_V2=true

Master kill-switch (overrides everything else):

    SURFSENSE_DISABLE_NEW_AGENT_STACK=true
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    """Parse a boolean env var. Accepts ``1``/``true``/``yes``/``on`` (case-insensitive)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class AgentFeatureFlags:
    """Resolved feature-flag state for one agent build.

    Constructed via :meth:`from_env`. The dataclass is frozen so it can be
    safely shared across coroutines.
    """

    # Master kill-switch — when true, every flag below resolves to False
    # regardless of its env value. Used for rapid rollback.
    disable_new_agent_stack: bool = False

    # Agent quality — context budget, retry/limits, name-repair, doom-loop
    enable_context_editing: bool = True
    enable_compaction_v2: bool = True
    enable_retry_after: bool = True
    enable_model_fallback: bool = False
    enable_model_call_limit: bool = True
    enable_tool_call_limit: bool = True
    enable_tool_call_repair: bool = True
    enable_doom_loop: bool = True

    # Safety — permissions, concurrency, tool-set narrowing
    enable_permission: bool = True
    enable_busy_mutex: bool = True
    enable_llm_tool_selector: bool = False  # Default OFF — adds per-turn LLM cost

    # Skills + subagents
    enable_skills: bool = True
    enable_specialized_subagents: bool = True
    enable_kb_planner_runnable: bool = True

    # Snapshot / revert
    enable_action_log: bool = True
    enable_revert_route: bool = True

    # Streaming parity v2 — opt in to LangChain's structured
    # ``AIMessageChunk`` content (typed reasoning blocks, tool-input
    # deltas) and propagate the real ``tool_call_id`` to the SSE layer.
    # When OFF the ``stream_new_chat`` task falls back to the str-only
    # text path and the synthetic ``call_<run_id>`` tool-call id (no
    # ``langchainToolCallId`` propagation). Schema migrations 135/136
    # ship unconditionally because they're forward-compatible.
    enable_stream_parity_v2: bool = True

    # Plugins
    enable_plugin_loader: bool = False

    # Observability — OTel (orthogonal; also requires OTEL_EXPORTER_OTLP_ENDPOINT)
    enable_otel: bool = False

    # Performance — compiled-agent cache (Phase 1 + Phase 2).
    # When ON, ``create_surfsense_deep_agent`` reuses a previously-compiled
    # graph if the cache key matches (LLM config + thread + tool surface +
    # flags + system prompt + filesystem mode). Cuts per-turn agent-build
    # wall clock from ~4-5s to <50µs on cache hits.
    #
    # SAFETY (Phase 2 unblocked this default-on):
    # All connector mutation tools (``tools/notion``, ``tools/gmail``,
    # ``tools/google_drive``, ``tools/dropbox``, ``tools/onedrive``,
    # ``tools/google_calendar``, ``tools/confluence``, ``tools/discord``,
    # ``tools/teams``, ``tools/luma``, ``connected_accounts``,
    # ``update_memory``, ``search_surfsense_docs``) now acquire fresh
    # short-lived ``AsyncSession`` instances per call via
    # :data:`async_session_maker`. The factory still accepts ``db_session``
    # for registry compatibility but ``del``'s it immediately — see any
    # of those files' factory docstrings for the rationale. The ``llm``
    # closure is per-(provider, model, config_id) which is already in
    # the cache key, so the LLM is safe to share across cached hits of
    # the same key. The KB priority middleware reads
    # ``mentioned_document_ids`` from ``runtime.context`` (Phase 1.5),
    # not its constructor closure, so the same compiled agent serves
    # turns with different mention lists correctly.
    #
    # Rollback: set ``SURFSENSE_ENABLE_AGENT_CACHE=false`` in the
    # environment if a regression surfaces. The path is exercised by
    # the ``tests/unit/agents/new_chat/test_agent_cache_*`` suite.
    enable_agent_cache: bool = True
    # Phase 1 (deferred — measure first): pre-build & share the
    # general-purpose subagent ``CompiledSubAgent`` across cold-cache
    # misses. Only helps when the outer cache MISSES (cache hits already
    # reuse the entire SubAgentMiddleware-compiled graph). Off by default
    # until we have data showing cold misses are frequent enough to
    # justify the extra global state.
    enable_agent_cache_share_gp_subagent: bool = False

    @classmethod
    def from_env(cls) -> AgentFeatureFlags:
        """Read flags from environment.

        Master kill-switch is evaluated first; when set, all other flags
        force to False.
        """
        master_off = _env_bool("SURFSENSE_DISABLE_NEW_AGENT_STACK", False)
        if master_off:
            logger.info(
                "SURFSENSE_DISABLE_NEW_AGENT_STACK is set: every new agent "
                "middleware is forced OFF for this build."
            )
            return cls(
                disable_new_agent_stack=True,
                enable_context_editing=False,
                enable_compaction_v2=False,
                enable_retry_after=False,
                enable_model_fallback=False,
                enable_model_call_limit=False,
                enable_tool_call_limit=False,
                enable_tool_call_repair=False,
                enable_doom_loop=False,
                enable_permission=False,
                enable_busy_mutex=False,
                enable_llm_tool_selector=False,
                enable_skills=False,
                enable_specialized_subagents=False,
                enable_kb_planner_runnable=False,
                enable_action_log=False,
                enable_revert_route=False,
                enable_stream_parity_v2=False,
                enable_plugin_loader=False,
                enable_otel=False,
                enable_agent_cache=False,
                enable_agent_cache_share_gp_subagent=False,
            )

        return cls(
            disable_new_agent_stack=False,
            # Agent quality
            enable_context_editing=_env_bool("SURFSENSE_ENABLE_CONTEXT_EDITING", True),
            enable_compaction_v2=_env_bool("SURFSENSE_ENABLE_COMPACTION_V2", True),
            enable_retry_after=_env_bool("SURFSENSE_ENABLE_RETRY_AFTER", True),
            enable_model_fallback=_env_bool("SURFSENSE_ENABLE_MODEL_FALLBACK", False),
            enable_model_call_limit=_env_bool(
                "SURFSENSE_ENABLE_MODEL_CALL_LIMIT", True
            ),
            enable_tool_call_limit=_env_bool("SURFSENSE_ENABLE_TOOL_CALL_LIMIT", True),
            enable_tool_call_repair=_env_bool(
                "SURFSENSE_ENABLE_TOOL_CALL_REPAIR", True
            ),
            enable_doom_loop=_env_bool("SURFSENSE_ENABLE_DOOM_LOOP", True),
            # Safety
            enable_permission=_env_bool("SURFSENSE_ENABLE_PERMISSION", True),
            enable_busy_mutex=_env_bool("SURFSENSE_ENABLE_BUSY_MUTEX", True),
            enable_llm_tool_selector=_env_bool(
                "SURFSENSE_ENABLE_LLM_TOOL_SELECTOR", False
            ),
            # Skills + subagents
            enable_skills=_env_bool("SURFSENSE_ENABLE_SKILLS", True),
            enable_specialized_subagents=_env_bool(
                "SURFSENSE_ENABLE_SPECIALIZED_SUBAGENTS", True
            ),
            enable_kb_planner_runnable=_env_bool(
                "SURFSENSE_ENABLE_KB_PLANNER_RUNNABLE", True
            ),
            # Snapshot / revert
            enable_action_log=_env_bool("SURFSENSE_ENABLE_ACTION_LOG", True),
            enable_revert_route=_env_bool("SURFSENSE_ENABLE_REVERT_ROUTE", True),
            # Streaming parity v2
            enable_stream_parity_v2=_env_bool(
                "SURFSENSE_ENABLE_STREAM_PARITY_V2", True
            ),
            # Plugins
            enable_plugin_loader=_env_bool("SURFSENSE_ENABLE_PLUGIN_LOADER", False),
            # Observability
            enable_otel=_env_bool("SURFSENSE_ENABLE_OTEL", False),
            # Performance
            enable_agent_cache=_env_bool("SURFSENSE_ENABLE_AGENT_CACHE", True),
            enable_agent_cache_share_gp_subagent=_env_bool(
                "SURFSENSE_ENABLE_AGENT_CACHE_SHARE_GP_SUBAGENT", False
            ),
        )

    def any_new_middleware_enabled(self) -> bool:
        """Return True if any new middleware flag is on."""
        if self.disable_new_agent_stack:
            return False
        return any(
            (
                self.enable_context_editing,
                self.enable_compaction_v2,
                self.enable_retry_after,
                self.enable_model_fallback,
                self.enable_model_call_limit,
                self.enable_tool_call_limit,
                self.enable_tool_call_repair,
                self.enable_doom_loop,
                self.enable_permission,
                self.enable_busy_mutex,
                self.enable_llm_tool_selector,
                self.enable_skills,
                self.enable_specialized_subagents,
                self.enable_kb_planner_runnable,
                self.enable_action_log,
                self.enable_revert_route,
                self.enable_plugin_loader,
            )
        )


# Module-level cache. Read once at import time so the values are consistent
# across the process lifetime. Use ``reload_for_tests`` to reset in tests.
_FLAGS: AgentFeatureFlags | None = None


def get_flags() -> AgentFeatureFlags:
    """Return the resolved feature-flag state, caching on first call."""
    global _FLAGS
    if _FLAGS is None:
        _FLAGS = AgentFeatureFlags.from_env()
    return _FLAGS


def reload_for_tests() -> AgentFeatureFlags:
    """Force a fresh read from env. Tests should call this after monkeypatching env."""
    global _FLAGS
    _FLAGS = AgentFeatureFlags.from_env()
    return _FLAGS


__all__ = [
    "AgentFeatureFlags",
    "get_flags",
    "reload_for_tests",
]
