"""Helper for wrapping a tool result with a Receipt in a ``Command(update=...)``.

Most mutating subagent tools historically returned a plain ``dict`` payload
which deepagents serialised straight into the ``ToolMessage`` content. To
participate in the verification teaching from
``multi_agent_chat/subagents/shared/snippets/verifiable_handle.md`` those
tools now also need to write a :class:`Receipt` into the parent's
``state['receipts']`` list (declared on
:class:`~app.agents.shared.filesystem_state.SurfSenseFilesystemState`
and backed by the append reducer).

:func:`with_receipt` wraps both behaviours: it returns the tool payload as
a JSON-encoded ``ToolMessage`` AND appends the receipt to state in a single
:class:`~langgraph.types.Command`. Use it at every ``return`` site of a
mutating tool — including failure paths (emit a receipt with
``status="failed"`` and the error message in ``error``).
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.agents.shared.receipt import Receipt


def _content_to_text(payload: dict[str, Any] | str) -> str:
    """Serialise a tool payload to ``ToolMessage`` content.

    Dicts go through ``json.dumps`` (matching deepagents' default tool-result
    serialisation); strings are passed through. Anything else is coerced via
    ``str`` so we never raise here — a mis-typed tool return would already
    have failed inside the tool body.
    """
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return json.dumps(payload, default=str)
    return str(payload)


def with_receipt(
    *,
    payload: dict[str, Any] | str,
    receipt: Receipt,
    tool_call_id: str,
) -> Command:
    """Return a Command that ships ``payload`` as a ToolMessage AND appends ``receipt``.

    The append happens via the ``_list_append_reducer`` on the ``receipts``
    field of :class:`~app.agents.shared.filesystem_state.SurfSenseFilesystemState`,
    so concurrent subagent batches (item 4 in the plan) won't clobber each
    other's receipts.
    """
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=_content_to_text(payload),
                    tool_call_id=tool_call_id,
                )
            ],
            "receipts": [receipt],
        }
    )


__all__ = ["with_receipt"]
