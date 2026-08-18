"""Resolve the root chat ``thread_id`` from a deliverables tool's runtime.

Deliverables tools run inside the ``deliverables`` subagent, which is invoked
with a *namespaced* ``thread_id`` of the form ``{chat_id}::task:{tool_call_id}``
(see :func:`subagent_invoke_config`). To attribute a generated deliverable
(artifact, podcast, image, or video) to the correct chat, we parse the leading
segment of that namespaced id rather than trusting a ``thread_id`` captured at
tool-build time — the latter would be stale once a single compiled agent graph
is reused across chats (cross-thread ``agent_cache`` reuse).
"""

from __future__ import annotations

from langchain.tools import ToolRuntime


def root_thread_id_from_config(config: object) -> int:
    """Return the root chat id from a LangGraph runnable config.

    A missing or malformed id is an invocation error. Falling back to a value
    captured when the graph was built can attribute one chat's output to
    another because compiled graphs are reused.
    """
    if not isinstance(config, dict):
        raise RuntimeError("Live chat thread configuration is unavailable")
    value = (config.get("configurable") or {}).get("thread_id")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value:
        root = value.split("::", 1)[0]
        try:
            return int(root)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Live chat thread id is invalid") from exc
    raise RuntimeError("Live chat thread id is unavailable")


def resolve_root_thread_id(runtime: ToolRuntime) -> int:
    """Return the root chat id from the live runtime config.

    The subagent's ``configurable.thread_id`` looks like ``"2099::task:call_x"``;
    the chat id is the segment before the first ``"::"``.
    """
    return root_thread_id_from_config(getattr(runtime, "config", None))
