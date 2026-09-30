"""What a plugin declares in its manifest.json."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from surfsense_plugin_manifest.rules.display_text import Description, DisplayName
from surfsense_plugin_manifest.rules.duplicate_names import unique_names
from surfsense_plugin_manifest.rules.hosts import Host
from surfsense_plugin_manifest.rules.identifiers import (
    EntryName,
    PluginId,
    VariableName,
)
from surfsense_plugin_manifest.rules.run_timeout import TimeoutSeconds


class Input(BaseModel):
    name: VariableName
    title: str
    kind: Literal["string", "number", "boolean"]
    required: bool = False


class Entry(BaseModel):
    name: EntryName
    title: str
    inputs: Annotated[list[Input], unique_names("inputs")]
    timeout_seconds: TimeoutSeconds = 1800


class Secret(BaseModel):
    name: VariableName
    title: str
    description: str | None = None


class Manifest(BaseModel):
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
    entries: Annotated[list[Entry], Field(min_length=1), unique_names("entries")]
