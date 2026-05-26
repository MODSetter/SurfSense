"""``InputsBlock`` — the ``inputs`` section of the automation definition."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InputsBlock(BaseModel):
    """The ``inputs`` block of an ``AutomationDefinition``.

    Holds a JSON Schema describing what data the automation accepts at
    fire time. The same schema is used by:

    - The form editor (to render the manual-run dialog).
    - The dispatcher (to validate trigger payloads before enqueueing
      executor work).
    - The template engine (to expose ``{{ inputs.* }}`` references in
      plan-step configs).

    The ``schema`` value is the JSON-Schema dict itself, not a
    Pydantic model — automations express their input contract in pure
    JSON Schema so it round-trips losslessly through the database and
    the NL generator.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_: dict[str, Any] = Field(
        ...,
        alias="schema",
        description=(
            "JSON Schema (draft-07 compatible) describing the inputs "
            "this automation accepts. Properties may use the special "
            "``$last_fired_at`` default literal to bind to the "
            "trigger's last fire time."
        ),
    )
