"""New-chat streaming flow.

The public entry point ``stream_new_chat`` is the slim coroutine in
``orchestrator.py`` that composes the per-concern modules in this folder and
the building blocks under ``flows/shared/``.
"""

from __future__ import annotations

from app.tasks.chat.streaming.flows.new_chat.orchestrator import stream_new_chat

__all__ = ["stream_new_chat"]
