"""The parts of the plugin's own manifest.json the SDK acts on.

Read as the app installed it, without the manifest rules: the app checked it before
the run, and the SDK depends on nothing.
"""

import json
from pathlib import Path
from typing import NotRequired, TypedDict, cast


class DeclaredInput(TypedDict):
    """An input, by the name its action function takes it under."""

    name: str


class DeclaredAction(TypedDict):
    """An action, and the inputs its function takes."""

    name: str
    inputs: list[DeclaredInput]


class DeclaredSecret(TypedDict):
    """A secret, by the name secret() checks against."""

    name: str


class PluginManifest(TypedDict):
    """The manifest.json fields the SDK acts on; the rest are the app's."""

    id: str
    # Stamped into the packaged copy by a release; absent in the repository.
    version: NotRequired[str]
    hosts: list[str]
    actions: list[DeclaredAction]
    secrets: NotRequired[list[DeclaredSecret]]


def read_plugin_manifest(folder: Path) -> PluginManifest:
    """Reads the manifest.json beside main.py, trusting the app checked it."""
    text = (folder / "manifest.json").read_text(encoding="utf-8")
    return cast(PluginManifest, json.loads(text))
