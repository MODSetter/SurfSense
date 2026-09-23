"""The shape of the committed remote manifest, checked when it is written and loaded."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

SCHEMA_VERSION = 1


class Modalities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: list[str]
    output: list[str]


class Call(BaseModel):
    """How a model is called, when it differs from its provider."""

    model_config = ConfigDict(extra="forbid")

    # Only /responses is recorded; the client speaks /chat/completions.
    route: Literal["responses"] | None = None
    # Another wire format entirely, such as "anthropic".
    protocol: str | None = None


class AccountField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str


class Connect(BaseModel):
    """How a connection reaches a provider."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "needs_account_details", "needs_url", "unreachable"]
    base_url: str | None
    base_url_origin: Literal["models.dev", "reviewed"] | None
    account_fields: list[AccountField]
    key: Literal["required", "none"]
    # A loopback server: no key, and no egress decision.
    local: bool
    reason: str | None


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
    call: Call | None


class RemoteProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    doc: str | None
    connect: Connect
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
