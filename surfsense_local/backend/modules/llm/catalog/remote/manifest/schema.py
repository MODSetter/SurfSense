"""The shape of the committed remote manifest, checked when it is written and loaded."""

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

SCHEMA_VERSION = 1


class Modalities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: list[str]
    output: list[str]


class RemoteModel(BaseModel):
    """One model as one provider serves it. None means models.dev never said."""

    model_config = ConfigDict(extra="forbid")

    name: str
    family: str | None
    description: str | None
    release_date: str | None
    # Open upstream vocabulary ("beta", "deprecated" today), so not a Literal.
    status: str | None
    modalities: Modalities
    context: int | None
    output_limit: int | None
    tool_call: bool | None
    reasoning: bool | None
    # Each option has its own shape ("effort" with values, "toggle" without).
    reasoning_options: list[dict[str, Any]] | None
    structured_output: bool | None
    temperature: bool | None


class RemoteProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    doc: str | None
    models: dict[str, RemoteModel]


class RemoteManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    source: str
    refreshed_at: str
    providers: dict[str, RemoteProvider]

    @model_validator(mode="after")
    def known_schema(self) -> "RemoteManifest":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported remote manifest schema: {self.schema_version}")
        return self
