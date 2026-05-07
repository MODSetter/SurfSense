"""Relay: thinking steps, tool bookkeeping, and ``EventRelay``.

Package imports are lazy so ``relay.thinking_step_sse`` (and siblings) can load
without pulling in ``event_relay`` (which imports handler modules that may
import those siblings).
"""

from __future__ import annotations

__all__ = ["EventRelay", "EventRelayConfig"]


def __getattr__(name: str):
    if name == "EventRelay":
        from app.tasks.chat.streaming.relay.event_relay import EventRelay

        return EventRelay
    if name == "EventRelayConfig":
        from app.tasks.chat.streaming.relay.event_relay import EventRelayConfig

        return EventRelayConfig
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
