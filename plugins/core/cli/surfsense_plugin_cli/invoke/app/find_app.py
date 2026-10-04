"""Finds the author's running SurfSense, so they never look up its port themselves."""

import os
from pathlib import Path

import typer

from surfsense_plugin_cli.invoke.app.app_api import answers

# Where a development app, then a packaged one, writes the address it answers at.
ANNOUNCED_IN = (".surfsense-dev", ".surfsense")


def find_app(api_url: str | None) -> str:
    """An address the author named must answer; otherwise the first app announced."""
    named = api_url or os.environ.get("SURFSENSE_PLUGIN_API_URL")
    candidates = [named] if named else [_announced(folder) for folder in ANNOUNCED_IN]
    for url in candidates:
        if url and answers(url.rstrip("/")):
            return url.rstrip("/")
    where = f" at {named}" if named else ""
    typer.echo(
        f"SurfSense is not running{where}: start it, or pass --api-url with the"
        " address it answers at",
        err=True,
    )
    raise typer.Exit(1)


def _announced(folder: str) -> str | None:
    """The address an app wrote when it started, if it is running now."""
    file = Path.home() / folder / "api-url"
    return file.read_text(encoding="utf-8").strip() if file.is_file() else None
