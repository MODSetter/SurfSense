"""surfsense-plugins new: what the author types, turned into a plugin folder."""

import json
import subprocess
from typing import Annotated

import typer
from pydantic import ValidationError
from surfsense_plugin_manifest import Manifest
from surfsense_plugin_manifest.errors.from_validation_errors import errors_from

from surfsense_plugin_cli.new.template import template
from surfsense_plugin_cli.repository import PLUGINS
from surfsense_plugin_cli.reserved_ids import is_reserved


def new(
    plugin: Annotated[
        str, typer.Argument(help="The new plugin's id, such as hn-search.")
    ],
) -> None:
    """Start a plugin in plugins/<id>, with one action that runs as it is.

    Example: surfsense-plugins new hn-search
    """
    folder = PLUGINS / plugin
    plugin_id = folder.name
    files = template(plugin_id, _authors_git_name())
    _refuse_what_it_cannot_take(plugin_id, json.loads(files["manifest.json"]))
    if folder.exists():
        typer.echo(f"{plugin_id} already exists at {folder}", err=True)
        raise typer.Exit(1)

    for relative, text in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    typer.echo(f"Created {folder}\nTry it:")
    typer.echo(f'  surfsense-plugins invoke {plugin_id} add-note --input text="Hello"')


def _refuse_what_it_cannot_take(plugin_id: str, manifest: dict[str, object]) -> None:
    """The same rules a pull request's checks apply, before anything is written."""
    if is_reserved(plugin_id):
        typer.echo(f"{plugin_id} is reserved for SurfSense's own plugins", err=True)
        raise typer.Exit(1)
    try:
        Manifest.model_validate(manifest)
    except ValidationError as broken:
        for error in errors_from(broken):
            typer.echo(f"{plugin_id}: {error}", err=True)
        raise typer.Exit(1) from None


def _authors_git_name() -> str:
    """Who the author already is to git, or nothing to fill in later."""
    try:
        found = subprocess.run(
            ["git", "config", "user.name"], capture_output=True, text=True
        )
    except FileNotFoundError:
        return ""
    return found.stdout.strip()
