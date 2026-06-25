"""Feature flags for the SurfSense new_chat agent stack.

Flags are resolved at agent build time. Most upgrades default ON so Docker
updates work without operators adding new env vars; risky integrations stay
OFF. The master kill-switch ``SURFSENSE_DISABLE_NEW_AGENT_STACK`` forces every
flag below to False for a one-switch rollback to pre-port behavior.
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

    # Snapshot / revert
    enable_action_log: bool = True
    enable_revert_route: bool = True

    # Plugins
    enable_plugin_loader: bool = False

    # Observability — OTel (orthogonal; also requires OTEL_EXPORTER_OTLP_ENDPOINT)
    enable_otel: bool = False

    # Performance — reuse a compiled agent graph when the cache key matches
    # (~4-5s -> <50µs per turn). Safe to default-on because mutation tools take
    # fresh short-lived sessions per call and per-turn context (mentions, etc.)
    # is read from runtime.context, not the constructor closure. Rollback via
    # SURFSENSE_ENABLE_AGENT_CACHE=false.
    enable_agent_cache: bool = True
    # Reuse one compiled graph across a returning user's *new* chats by dropping
    # ``thread_id`` from the agent_cache key. Safe because every middleware/tool
    # that needs the chat thread now resolves it from the live RunnableConfig
    # (ActionLog, KB-persistence, deliverables) rather than a constructor
    # closure, and mutation tools open fresh per-call sessions. Turns a
    # returning user's cold first turn into a cache hit (cold == warm).
    # Rollback via SURFSENSE_ENABLE_CROSS_THREAD_AGENT_CACHE=false.
    enable_cross_thread_agent_cache: bool = True
    # Deferred: only helps on outer-cache MISSES, so off until data shows cold
    # misses are frequent enough to justify the extra global state.
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
                enable_action_log=False,
                enable_revert_route=False,
                enable_plugin_loader=False,
                enable_otel=False,
                enable_agent_cache=False,
                enable_cross_thread_agent_cache=False,
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
            # Snapshot / revert
            enable_action_log=_env_bool("SURFSENSE_ENABLE_ACTION_LOG", True),
            enable_revert_route=_env_bool("SURFSENSE_ENABLE_REVERT_ROUTE", True),
            # Plugins
            enable_plugin_loader=_env_bool("SURFSENSE_ENABLE_PLUGIN_LOADER", False),
            # Observability
            enable_otel=_env_bool("SURFSENSE_ENABLE_OTEL", False),
            # Performance
            enable_agent_cache=_env_bool("SURFSENSE_ENABLE_AGENT_CACHE", True),
            enable_cross_thread_agent_cache=_env_bool(
                "SURFSENSE_ENABLE_CROSS_THREAD_AGENT_CACHE", True
            ),
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
                self.enable_action_log,
                self.enable_revert_route,
                self.enable_plugin_loader,
            )
        )


def get_flags() -> AgentFeatureFlags:
    """Return the resolved feature-flag state from the **current** process environment.

    Intentionally **not** cached: ``load_dotenv`` and operator edits to env vars
    must affect the next agent build without requiring a full process restart.
    Cost is negligible (reads ``os.environ`` once per call).
    """
    return AgentFeatureFlags.from_env()


def reload_for_tests() -> AgentFeatureFlags:
    """Compatibility helper for tests; equivalent to :func:`get_flags`."""
    return AgentFeatureFlags.from_env()


__all__ = [
    "AgentFeatureFlags",
    "get_flags",
    "reload_for_tests",
]
