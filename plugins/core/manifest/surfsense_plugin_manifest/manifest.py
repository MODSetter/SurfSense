"""What a plugin declares in its manifest.json."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from surfsense_plugin_manifest.rules.display_text import Description, DisplayName
from surfsense_plugin_manifest.rules.duplicate_names import unique_names
from surfsense_plugin_manifest.rules.hosts import Host
from surfsense_plugin_manifest.rules.identifiers import (
    ActionName,
    PluginId,
    VariableName,
)
from surfsense_plugin_manifest.rules.run_timeout import TimeoutSeconds


class Input(BaseModel):
    """A value the user gives each time an action runs."""

    name: VariableName
    title: str
    kind: Literal["string", "number", "boolean"]
    required: bool = False


class Action(BaseModel):
    """A function the app can run, and what it asks the user for."""

    name: ActionName
    title: str
    inputs: Annotated[list[Input], unique_names("inputs")]
    timeout_seconds: TimeoutSeconds = 1800


class Secret(BaseModel):
    """A value the user enters once in Settings, never shown again."""

    name: VariableName
    title: str
    description: str | None = None


class Manifest(BaseModel):
    """What a plugin declares about itself in manifest.json."""

    id: PluginId
    # Written by the release into the downloaded copy; an author never writes it.
    version: str | None = None
    name: DisplayName
    description: Description
    author: str
    access: Literal["free", "paid"]
    hosts: list[Host]
    secrets: Annotated[list[Secret], unique_names("secrets")] = []
    platforms: list[str] | None = None
    actions: Annotated[list[Action], Field(min_length=1), unique_names("actions")]
