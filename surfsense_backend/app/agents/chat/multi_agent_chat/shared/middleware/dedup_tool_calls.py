"""Dedup-key resolvers for tool-call deduplication.

A *resolver* maps a tool's ``args`` dict to a stable signature string used to
collapse duplicate calls. These helpers are shared: the MCP tool layer uses
:func:`dedup_key_full_args` as a safe default, and the main-agent
``DedupHITLToolCallsMiddleware`` builds its resolver map from them.

Resolver resolution order (read from each tool's own ``metadata``):

1. ``tool.metadata["dedup_key"]`` — callable mapping the args dict to a
   stable signature string. This is the canonical mechanism.
2. ``tool.metadata["hitl_dedup_key"]`` — string naming a primary arg;
   used by MCP / Composio tools that only expose a single key field.

A tool with no resolver from either path simply opts out of dedup.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

# Resolver type — given the tool ``args`` dict returns a stable
# string used to dedupe consecutive calls. ``None`` means no dedup.
DedupResolver = Callable[[dict[str, Any]], str]


def wrap_dedup_key_by_arg_name(arg_name: str) -> DedupResolver:
    """Adapt a string-arg name into a :data:`DedupResolver`.

    Convenience helper for tools that just want to dedupe on a single arg's
    lowercased value (the most common case for HITL tools like
    ``send_gmail_email`` keyed on ``subject``). Set the result on the tool's
    ``metadata["dedup_key"]``.
    """

    def _resolver(args: dict[str, Any]) -> str:
        return str(args.get(arg_name, "")).lower()

    return _resolver


def dedup_key_full_args(args: dict[str, Any]) -> str:
    """Resolver that collapses calls only when **every** argument is identical.

    Safe default for tools where no single field uniquely identifies a call
    (e.g. MCP tools whose first required field is a shared workspace id).
    """

    try:
        return json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return repr(sorted(args.items())) if isinstance(args, dict) else repr(args)


# Backwards-compatible alias for code that imported the original
# private name. New callers should use :func:`wrap_dedup_key_by_arg_name`.
_wrap_string_key = wrap_dedup_key_by_arg_name
