"""The surfsense-plugins command, one subcommand per job."""

import typer

from surfsense_plugin_cli.dependencies.add import add
from surfsense_plugin_cli.dependencies.pin_dependencies import pin_dependencies
from surfsense_plugin_cli.dependencies.remove import remove
from surfsense_plugin_cli.invoke.command import invoke
from surfsense_plugin_cli.new.command import new

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


@app.callback()
def surfsense_plugins() -> None:
    """Write, try and check SurfSense plugins."""


app.command()(new)
app.command()(add)
app.command()(remove)
app.command(name="pin-dependencies")(pin_dependencies)
app.command()(invoke)
