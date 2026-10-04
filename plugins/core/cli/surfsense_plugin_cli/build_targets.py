"""What plugins are built for: the app's Python and its platforms, from build-targets.json."""

import json
import platform
import sys
from dataclasses import dataclass

import typer

from surfsense_plugin_cli.repository import CORE


@dataclass(frozen=True)
class BuildTargets:
    """The Python version, and each platform's key with the uv target it installs for."""

    python: str
    platforms: dict[str, str]


def build_targets() -> BuildTargets:
    """Read fresh each time: the file is the one list packaging, checks and the app share."""
    declared = json.loads((CORE / "build-targets.json").read_text(encoding="utf-8"))
    return BuildTargets(declared["python"], declared["platforms"])


def this_platform() -> str:
    """This machine's key, such as linux-x64, if plugins are built for it."""
    arm = platform.machine().lower() in ("arm64", "aarch64")
    system = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(
        sys.platform, sys.platform
    )
    key = f"{system}-{'arm64' if arm else 'x64'}"
    supported = build_targets().platforms
    if key not in supported:
        typer.echo(
            f"plugins are built for {', '.join(supported)}; this machine is {key}",
            err=True,
        )
        raise typer.Exit(1)
    return key
