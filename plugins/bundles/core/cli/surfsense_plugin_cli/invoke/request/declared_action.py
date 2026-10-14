"""The action the author named, as the plugin's manifest declares it."""

import typer
from surfsense_plugin_manifest import Action

from surfsense_plugin_cli.plugin_folder import PluginFolder


def declared_action(folder: PluginFolder, name: str) -> Action:
    """Refused by name, with the actions the plugin does have."""
    for action in folder.manifest.actions:
        if action.name == name:
            return action
    offered = ", ".join(action.name for action in folder.manifest.actions)
    typer.echo(
        f'{folder.manifest.id} has no action named "{name}": its actions are {offered}',
        err=True,
    )
    raise typer.Exit(1)
