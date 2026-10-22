"""One plugin as a list describes it: the schema the first-party list and the registry share."""

import ipaddress
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

# MCP's own rule for a tool name.
ToolName = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")]


class EntryHeader(BaseModel):
    """A header the user's key goes in; the entry names and words it, never a value."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str
    # Put before the value the user types, such as `Bearer `.
    prefix: str | None = None
    label: str | None = None
    description: str | None = None


class EntryAuth(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: Literal["none", "token", "headers", "oauth", "license"]
    title: str | None = None
    description: str | None = None
    headers: list[EntryHeader] | None = None
    # OAuth only: SurfSense's app where a provider registers clients in advance. Never a secret.
    client_id: str | None = None
    scopes: list[str] | None = None
    # OAuth only: the provider takes only apps registered in advance; the user brings theirs.
    user_client: bool = False


class ListEntry(BaseModel):
    """Unknown fields are ignored, so a list written for a newer app loads in an older one."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    kind: Literal["remote"]
    # Registry only: `verified` when a maintainer judged in review that its author runs
    # the server. A first-party entry has none: it is SurfSense's by its list.
    verification: Literal["verified", "community"] | None = None
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=80)
    url: str
    auth: EntryAuth
    hosts: list[str] = Field(min_length=1)
    access: Literal["free", "external", "license"]
    access_note: str | None = None
    privacy_policy: str | None = None
    homepage: str | None = None
    icon: str | None = None
    # What the plugin's page shows before it is connected.
    about: str | None = Field(default=None, min_length=1, max_length=600)
    # The server's tool names, shown before it is connected; never given to a model.
    tools: list[ToolName] | None = None
    # The month the plugin joined its list, as `YYYY-MM`.
    added: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")

    @model_validator(mode="after")
    def _reachable_as_listed(self) -> Self:
        parts = urlsplit(self.url)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError("url must be https")
        if parts.username or parts.password:
            raise ValueError("url must hold no credentials")
        if parts.hostname not in self.hosts:
            raise ValueError("hosts must name the url's host")
        if any(_is_loopback(host) for host in self.hosts):
            raise ValueError("hosts must not be loopback")
        if self.access == "external" and not self.access_note:
            raise ValueError("access_note is required when access is external")
        if self.tools and len(set(self.tools)) != len(self.tools):
            raise ValueError("tools lists a tool twice")
        return self


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
