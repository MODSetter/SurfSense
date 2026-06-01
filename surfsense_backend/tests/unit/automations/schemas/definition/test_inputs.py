"""Lock the ``Inputs`` JSON ``schema``-alias roundtrip.

The field is ``schema_`` in Python (``schema`` shadows a Pydantic builtin)
but is wire-named ``schema``. Locking the roundtrip means JSON definitions
authored anywhere (UI raw editor, NL drafter, CLI export) speak the same
wire shape.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.automations.schemas.definition.inputs import Inputs

pytestmark = pytest.mark.unit


def test_inputs_parses_wire_field_named_schema_into_schema_attribute() -> None:
    """JSON payloads use ``schema`` (the convention). The model stores it
    on the Python attribute ``schema_`` without shadowing the builtin."""
    parsed = Inputs.model_validate({"schema": {"type": "object"}})

    assert parsed.schema_ == {"type": "object"}


def test_inputs_serializes_schema_attribute_back_to_wire_field_named_schema() -> None:
    """Round-trip: serializing emits ``schema`` (alias), not ``schema_``.
    Locks the consumer-visible JSON shape regardless of the Python name."""
    inputs = Inputs(schema={"type": "object"})  # type: ignore[call-arg]

    assert inputs.model_dump() == {"schema": {"type": "object"}}


def test_inputs_rejects_unknown_field() -> None:
    """``extra='forbid'`` catches typos like ``shema`` so bad definitions
    don't silently lose their input declaration."""
    with pytest.raises(ValidationError):
        Inputs.model_validate({"schema": {}, "extra": "x"})
