"""Finds a plugin's folder from what the author typed, and loads its manifest."""

from dataclasses import dataclass
from pathlib import Path

import typer
from surfsense_plugin_manifest import Manifest, ManifestError, load_manifest

from surfsense_plugin_cli.repository import PLUGINS


@dataclass(frozen=True)
class PluginFolder:
    """A plugin's folder, with a manifest that follows every rule."""

    path: Path
    manifest: Manifest


def plugin_folder(plugin: str) -> PluginFolder:
    """An id such as hn-search names a folder in plugins/; a path names itself."""
    path = PLUGINS / plugin
    if not (path / "manifest.json").is_file():
        typer.echo(f"no plugin at {path}: it needs a manifest.json", err=True)
        raise typer.Exit(1)
    try:
        manifest = load_manifest(path / "manifest.json")
    except ManifestError as refused:
        for error in refused.errors:
            typer.echo(f"manifest.json: {error}", err=True)
        raise typer.Exit(1) from None
    return PluginFolder(path, manifest)
