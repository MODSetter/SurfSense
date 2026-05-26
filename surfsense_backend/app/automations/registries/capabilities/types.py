"""``Capability`` dataclass — the v1-minimum five-field shape."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

CapabilityHandler = Callable[[dict[str, Any]], Awaitable[Any]]
"""The signature every capability handler must satisfy.

The handler is a closure that already holds whatever runtime context
it needs (DB session, search-space scope, logger, etc.). The
registry only passes through the caller's input dict — the same dict
that was validated against ``input_schema``.
"""


@dataclass(frozen=True, slots=True)
class Capability:
    """The unit of "what SurfSense can do," consumed by every layer.

    v1 keeps the dataclass to exactly five fields. Earlier drafts
    considered ``name``, ``required_credentials``, ``side_effects``,
    ``expected_duration_seconds``, and ``cost_estimate``; every one
    of those has been removed until a concrete consumer feature
    requires it (see ``automation-design-plan.md`` §3, decision v1).

    The handler is a ready-to-call function. It does not receive a
    context argument — context is bound at registration time by the
    factory that builds the closure (so a capability returned to an
    agent's tool list looks identical to one returned to an
    automation's action runtime).
    """

    id: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: CapabilityHandler
