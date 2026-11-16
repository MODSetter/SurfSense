"""Picks the workspace a run writes to, and never guesses between several."""

from dataclasses import dataclass
from typing import TypedDict, cast

import typer

from surfsense_plugin_cli.invoke.app.app_api import read_from_app


@dataclass(frozen=True)
class Workspace:
    """A workspace of the running app, named so the author sees where a run writes."""

    id: int
    name: str


class _Listed(TypedDict):
    id: int
    name: str


def choose_workspace(api_url: str, workspace: int | None) -> Workspace:
    """The one the author named, else the app's only one; otherwise it asks."""
    listed = cast(list[_Listed], read_from_app(api_url, "/workspaces"))
    workspaces = [Workspace(each["id"], each["name"]) for each in listed]
    if workspace is None and len(workspaces) == 1:
        return workspaces[0]
    for each in workspaces:
        if each.id == workspace:
            return each

    typer.echo(
        "SurfSense has several workspaces: pass --workspace with one of these ids"
        if workspace is None
        else f"SurfSense has no workspace {workspace}: pass --workspace with one of"
        " these ids",
        err=True,
    )
    for each in workspaces:
        typer.echo(f"  {each.id}  {each.name}", err=True)
    raise typer.Exit(1)
