"""surfsense-plugins pin-dependencies: pins again what requirements.in lists."""

from typing import Annotated

import typer

from surfsense_plugin_cli.dependencies.listed import listed
from surfsense_plugin_cli.dependencies.rewrite_and_pin import rewrite_and_pin
from surfsense_plugin_cli.plugin_folder import plugin_folder


def pin_dependencies(
    plugin: Annotated[
        str, typer.Argument(help="The plugin's id, such as hn-search, or its folder.")
    ],
) -> None:
    """Pin a plugin's dependencies again, after editing requirements.in by hand.

    Example: surfsense-plugins pin-dependencies hn-search
    """
    folder = plugin_folder(plugin)
    lines = listed(folder.path)
    if not lines:
        typer.echo(
            f"{folder.manifest.id} lists no dependencies: add one with"
            f" surfsense-plugins add {folder.manifest.id} <library>",
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(f"{rewrite_and_pin(folder, lines)}.")
