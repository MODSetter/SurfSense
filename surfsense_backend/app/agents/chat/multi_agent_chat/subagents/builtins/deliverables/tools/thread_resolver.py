"""Resolve the root chat ``thread_id`` from a deliverables tool's runtime.

Deliverables tools run inside the ``deliverables`` subagent, which is invoked
with a *namespaced* ``thread_id`` of the form ``{chat_id}::task:{tool_call_id}``
(see :func:`subagent_invoke_config`). To attribute a generated deliverable
(podcast / report / resume / video) to the correct chat, we parse the leading
segment of that namespaced id rather than trusting a ``thread_id`` captured at
tool-build time — the latter would be stale once a single compiled agent graph
is reused across chats (cross-thread ``agent_cache`` reuse).
"""

from __future__ import annotations

from langchain.tools import ToolRuntime


def resolve_root_thread_id(runtime: ToolRuntime, fallback: int | None) -> int | None:
    """Return the root chat id from the live runtime config, else ``fallback``.

    The subagent's ``configurable.thread_id`` looks like ``"2099::task:call_x"``;
    the chat id is the segment before the first ``"::"``. Returns ``fallback``
    when the config is absent or the leading segment is not an integer.
    """
    try:
        config = getattr(runtime, "config", None)
        if not isinstance(config, dict):
            return fallback
        value = (config.get("configurable") or {}).get("thread_id")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value:
            root = value.split("::", 1)[0]
            try:
                return int(root)
            except (TypeError, ValueError):
                return fallback
    except Exception:  # pragma: no cover - defensive
        return fallback
    return fallback
