"""
Feature flags for the SurfSense new_chat agent stack.

These flags gate the newer agent middleware (some ported from OpenCode,
some sourced from ``langchain.agents.middleware`` / ``deepagents``, some
SurfSense-native). They follow a "default-OFF for risky things,
default-ON for safe upgrades, master kill-switch for everything new" model.

All new middleware checks its flag at agent build time. If the master
kill-switch ``SURFSENSE_DISABLE_NEW_AGENT_STACK`` is set, every new
middleware is disabled regardless of its individual flag. This gives
operators a single switch to revert to pre-port behavior.

Examples
--------

Local development (recommended for trying everything except doom-loop / selector):

    SURFSENSE_ENABLE_CONTEXT_EDITING=true
    SURFSENSE_ENABLE_COMPACTION_V2=true
    SURFSENSE_ENABLE_RETRY_AFTER=true
    SURFSENSE_ENABLE_TOOL_CALL_REPAIR=true
    SURFSENSE_ENABLE_PERMISSION=false   # default off, opt-in per deploy
    SURFSENSE_ENABLE_DOOM_LOOP=false    # default off until UI ships
    SURFSENSE_ENABLE_LLM_TOOL_SELECTOR=false
    SURFSENSE_ENABLE_STREAM_PARITY_V2=false  # structured streaming events

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
    enable_context_editing: bool = False
    enable_compaction_v2: bool = False
    enable_retry_after: bool = False
    enable_model_fallback: bool = False
    enable_model_call_limit: bool = False
    enable_tool_call_limit: bool = False
    enable_tool_call_repair: bool = False
    enable_doom_loop: bool = (
        False  # Default OFF until UI handles permission='doom_loop'
    )

    # Safety — permissions, concurrency, tool-set narrowing
    enable_permission: bool = False  # Default OFF for first deploy
    enable_busy_mutex: bool = False
    enable_llm_tool_selector: bool = False  # Default OFF — adds per-turn LLM cost

    # Skills + subagents
    enable_skills: bool = False
    enable_specialized_subagents: bool = False
    enable_kb_planner_runnable: bool = False

    # Snapshot / revert
    enable_action_log: bool = False
    enable_revert_route: bool = (
        False  # Backend ships before UI; route returns 503 until this flips
    )

    # Streaming parity v2 — opt in to LangChain's structured
    # ``AIMessageChunk`` content (typed reasoning blocks, tool-input
    # deltas) and propagate the real ``tool_call_id`` to the SSE layer.
    # When OFF the ``stream_new_chat`` task falls back to the str-only
    # text path and the synthetic ``call_<run_id>`` tool-call id (no
    # ``langchainToolCallId`` propagation). Schema migrations 135/136
    # ship unconditionally because they're forward-compatible.
    enable_stream_parity_v2: bool = False

    # Plugins
    enable_plugin_loader: bool = False

    # Observability — OTel (orthogonal; also requires OTEL_EXPORTER_OTLP_ENDPOINT)
    enable_otel: bool = False

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
            return cls(disable_new_agent_stack=True)

        return cls(
            disable_new_agent_stack=False,
            # Agent quality
            enable_context_editing=_env_bool("SURFSENSE_ENABLE_CONTEXT_EDITING", False),
            enable_compaction_v2=_env_bool("SURFSENSE_ENABLE_COMPACTION_V2", False),
            enable_retry_after=_env_bool("SURFSENSE_ENABLE_RETRY_AFTER", False),
            enable_model_fallback=_env_bool("SURFSENSE_ENABLE_MODEL_FALLBACK", False),
            enable_model_call_limit=_env_bool(
                "SURFSENSE_ENABLE_MODEL_CALL_LIMIT", False
            ),
            enable_tool_call_limit=_env_bool("SURFSENSE_ENABLE_TOOL_CALL_LIMIT", False),
            enable_tool_call_repair=_env_bool(
                "SURFSENSE_ENABLE_TOOL_CALL_REPAIR", False
            ),
            enable_doom_loop=_env_bool("SURFSENSE_ENABLE_DOOM_LOOP", False),
            # Safety
            enable_permission=_env_bool("SURFSENSE_ENABLE_PERMISSION", False),
            enable_busy_mutex=_env_bool("SURFSENSE_ENABLE_BUSY_MUTEX", False),
            enable_llm_tool_selector=_env_bool(
                "SURFSENSE_ENABLE_LLM_TOOL_SELECTOR", False
            ),
            # Skills + subagents
            enable_skills=_env_bool("SURFSENSE_ENABLE_SKILLS", False),
            enable_specialized_subagents=_env_bool(
                "SURFSENSE_ENABLE_SPECIALIZED_SUBAGENTS", False
            ),
            enable_kb_planner_runnable=_env_bool(
                "SURFSENSE_ENABLE_KB_PLANNER_RUNNABLE", False
            ),
            # Snapshot / revert
            enable_action_log=_env_bool("SURFSENSE_ENABLE_ACTION_LOG", False),
            enable_revert_route=_env_bool("SURFSENSE_ENABLE_REVERT_ROUTE", False),
            # Streaming parity v2
            enable_stream_parity_v2=_env_bool(
                "SURFSENSE_ENABLE_STREAM_PARITY_V2", False
            ),
            # Plugins
            enable_plugin_loader=_env_bool("SURFSENSE_ENABLE_PLUGIN_LOADER", False),
            # Observability
            enable_otel=_env_bool("SURFSENSE_ENABLE_OTEL", False),
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
