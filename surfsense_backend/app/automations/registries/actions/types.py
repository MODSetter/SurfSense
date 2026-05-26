"""``ActionDefinition`` dataclass — the v1-minimum action shape."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

ActionHandler = Callable[[dict[str, Any]], Awaitable[Any]]
"""The signature every action handler must satisfy.

Identical in shape to ``CapabilityHandler`` — both receive a
caller-validated input dict and return an arbitrary output. The
distinction is purely architectural: capabilities are the low-level
"what SurfSense can do" surface, actions are the user-facing
building blocks composed into a plan.
"""


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    """A user-facing step type the plan editor can compose.

    v1 trims the dataclass to the five fields necessary for
    registry dispatch and form rendering. The full design (§4)
    includes ``output_contract``, ``uses_capabilities``, and
    ``produces_artifacts``; all three are deferred until a consumer
    feature requires them:

    - ``output_contract`` — the loose ``agent_task`` action declares
      its output shape per-step via ``config.output_schema``, so the
      action-level contract is not needed in v1.
    - ``uses_capabilities`` — would let the NL generator do static
      analysis of which capabilities each action invokes; deferred
      because v1 ships a single (``agent_task``) action.
    - ``produces_artifacts`` — deferred alongside the artifact
      pipeline (see §13 decision 26).
    """

    type: str
    name: str
    description: str
    config_schema: dict[str, Any]
    handler: ActionHandler
