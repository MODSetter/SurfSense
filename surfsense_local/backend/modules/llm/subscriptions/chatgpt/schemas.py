from typing import Self

from pydantic import BaseModel, Field, model_validator

from modules.llm.subscriptions.chatgpt.flows import FlowStatus


class SignInWrite(BaseModel):
    """A new connection's label, or the connection whose sign-in this renews."""

    label: str | None = Field(default=None, min_length=1, max_length=100)
    connection_id: int | None = None

    @model_validator(mode="after")
    def one_target(self) -> Self:
        if (self.label is None) == (self.connection_id is None):
            raise ValueError("give either a label or a connection_id")
        if self.label is not None and not self.label.strip():
            raise ValueError("label must not be empty")
        return self


class SignInStarted(BaseModel):
    flow_id: str
    # Opened in the system browser; it holds no secret, only the PKCE challenge.
    authorize_url: str


class SignInRead(BaseModel):
    status: FlowStatus
    connection_id: int | None
    message: str | None


class SignInHost(BaseModel):
    """A host the sign-in reaches that egress has not allowed yet."""

    destination: str
    host: str
