"""Single-responsibility split of the streaming SSE protocol.

Layout:
* ``envelope/`` - SSE wire framing + ID generators
* ``emitter/`` - identity of the agent that emitted an event + runtime registry
* ``events/`` - one module per SSE event family
* ``service.py`` - composition root used by the orchestrator
* ``interrupt_correlation.py`` - id-aware lookup over LangGraph state

Naming on the wire:
* AI SDK protocol fields keep their existing camelCase
  (``toolCallId``, ``messageId``, ``inputTextDelta``, ``langchainToolCallId``).
* Every SurfSense-added field uses ``snake_case``, including the
  top-level ``emitted_by`` envelope and all inner ``data`` payloads.

Production keeps using ``app.services.new_streaming_service`` and
``app.tasks.chat.stream_new_chat`` until the cutover phase.
"""

from __future__ import annotations
