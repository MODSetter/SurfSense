"""``InputsBlock`` — JSON Schema for inputs an automation accepts at fire time."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InputsBlock(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_: dict[str, Any] = Field(
        ...,
        alias="schema",
        description="JSON Schema (draft 2020-12) for accepted inputs.",
    )
