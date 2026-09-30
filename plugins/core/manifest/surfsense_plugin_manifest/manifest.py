"""What a plugin declares in its manifest.json."""

from typing import Literal

from pydantic import BaseModel, Field

from surfsense_plugin_manifest.rules.display_text import Description, DisplayName
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
    inputs: list[Input]
    timeout_seconds: TimeoutSeconds = 1800


class Secret(BaseModel):
    name: VariableName
    title: str
    description: str | None = None


class Manifest(BaseModel):
    id: PluginId
    name: DisplayName
    description: Description
    author: str
    access: Literal["free", "paid"]
    hosts: list[Host]
    secrets: list[Secret] = []
    platforms: list[str] | None = None
    entries: list[Entry] = Field(min_length=1)
