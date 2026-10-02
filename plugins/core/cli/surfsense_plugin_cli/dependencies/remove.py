"""surfsense-plugins remove: a library the plugin no longer needs."""

from typing import Annotated

import typer

from surfsense_plugin_cli.dependencies.listed import library_name, listed
from surfsense_plugin_cli.dependencies.rewrite_and_pin import rewrite_and_pin
from surfsense_plugin_cli.plugin_folder import plugin_folder


def remove(
    plugin: Annotated[
        str, typer.Argument(help="The plugin's id, such as hn-search, or its folder.")
    ],
    names: Annotated[list[str], typer.Argument(help="A library the plugin lists.")],
) -> None:
    """Remove libraries from a plugin, and pin what remains.

    Example: surfsense-plugins remove hn-search lxml
    """
    folder = plugin_folder(plugin)
    lines = listed(folder.path)
    for name in names:
        kept = [line for line in lines if library_name(line) != library_name(name)]
        if kept == lines:
            typer.echo(f"{folder.manifest.id} does not list {name}", err=True)
            raise typer.Exit(1)
        lines = kept
    pinned = rewrite_and_pin(folder, lines)
    typer.echo(f"Removed {', '.join(names)}: {pinned}.")
