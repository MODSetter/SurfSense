"""surfsense-plugins invoke: what the author types, turned into one run."""

from typing import Annotated

import typer

from surfsense_plugin_cli.invoke.app.choose_workspace import choose_workspace
from surfsense_plugin_cli.invoke.app.find_app import find_app
from surfsense_plugin_cli.invoke.plugin.dependencies import install_dependencies
from surfsense_plugin_cli.invoke.plugin.run_plugin import run_plugin
from surfsense_plugin_cli.invoke.plugin.secrets import secrets_for
from surfsense_plugin_cli.invoke.request.declared_action import declared_action
from surfsense_plugin_cli.invoke.request.inputs import inputs_for
from surfsense_plugin_cli.plugin_folder import plugin_folder


def invoke(
    plugin: Annotated[
        str, typer.Argument(help="The plugin's id, such as hn-search, or its folder.")
    ],
    action: Annotated[str, typer.Argument(help="The action to run, as named.")],
    inputs: Annotated[
        list[str] | None,
        typer.Option("--input", help="name=value, once per input."),
    ] = None,
    workspace: Annotated[
        int | None, typer.Option(help="The workspace the plugin writes to.")
    ] = None,
    api_url: Annotated[
        str | None, typer.Option(help="Where your SurfSense answers.")
    ] = None,
) -> None:
    """Run one action of a plugin once, against your running SurfSense.

    Example: surfsense-plugins invoke example count-words --input text="a b a"
    """
    folder = plugin_folder(plugin)
    given = inputs_for(declared_action(folder, action), inputs or [])
    install_dependencies(folder.path)
    app = find_app(api_url)
    chosen = choose_workspace(app, workspace)
    context = {
        "SURFSENSE_PLUGIN_API_URL": app,
        "SURFSENSE_PLUGIN_WORKSPACE_ID": str(chosen.id),
        "SURFSENSE_PLUGIN_ID": folder.manifest.id,
    } | secrets_for(folder.manifest)

    # On stderr, so what the plugin prints stays the command's only output.
    typer.echo(
        f'Running {action} of {folder.manifest.id} in "{chosen.name}" at {app}',
        err=True,
    )
    code = run_plugin(folder.path, action, given, context)
    typer.echo("Done." if code == 0 else f"Failed: exit {code}.", err=True)
    raise typer.Exit(code)
