"""surfsense-plugins add: a library the plugin needs, listed and pinned."""

from typing import Annotated

import typer

from surfsense_plugin_cli.dependencies.listed import library_name, listed
from surfsense_plugin_cli.dependencies.rewrite_and_pin import rewrite_and_pin
from surfsense_plugin_cli.plugin_folder import plugin_folder


def add(
    plugin: Annotated[
        str, typer.Argument(help="The plugin's id, such as hn-search, or its folder.")
    ],
    requirements: Annotated[
        list[str], typer.Argument(help="A library, such as lxml or 'requests>=2'.")
    ],
) -> None:
    """Add libraries to a plugin, pinned for every platform it runs on.

    Example: surfsense-plugins add hn-search lxml
    """
    folder = plugin_folder(plugin)
    lines = listed(folder.path)
    for requirement in requirements:
        name = library_name(requirement)
        # A library already listed takes the new version range in its place.
        lines = [line for line in lines if library_name(line) != name]
        lines.append(requirement)
    pinned = rewrite_and_pin(folder, lines)
    typer.echo(f"Added {', '.join(requirements)} to {folder.manifest.id}: {pinned}.")
