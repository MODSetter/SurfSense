"""Writes requirements.in and pins requirements.txt from it, the one way all three commands do."""

import re
import subprocess

import typer
from uv import find_uv_bin

from surfsense_plugin_cli.build_targets import build_targets
from surfsense_plugin_cli.plugin_folder import PluginFolder

FILES = ("requirements.in", "requirements.txt")


def rewrite_and_pin(plugin: PluginFolder, lines: list[str]) -> str:
    """Both files updated together, or both put back as they were.

    Returns what is pinned now, in words, for the command to tell the author.
    """
    before = {name: _read(plugin, name) for name in FILES}
    if not lines:
        for name in FILES:
            (plugin.path / name).unlink(missing_ok=True)
        return f"{plugin.manifest.id} has no dependencies left"
    (plugin.path / "requirements.in").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    refused = _pin(plugin)
    if refused:
        for name, text in before.items():
            _restore(plugin, name, text)
        typer.echo(f"the dependencies cannot be pinned:\n{refused}", err=True)
        raise typer.Exit(1)
    pinned = _pinned_packages(plugin)
    return f"requirements.txt pins {pinned} package{'' if pinned == 1 else 's'}"


def _pin(plugin: PluginFolder) -> str | None:
    """Every version and file hash, for every platform. uv's reason when it cannot.

    uv keeps what requirements.txt already pins, so one change upgrades nothing else.
    """
    finished = subprocess.run(
        [
            find_uv_bin(),
            "pip",
            "compile",
            "--quiet",
            "--universal",
            "--generate-hashes",
            "--python-version",
            build_targets().python,
            "--custom-compile-command",
            f"surfsense-plugins pin-dependencies {plugin.manifest.id}",
            "requirements.in",
            "--output-file",
            "requirements.txt",
        ],
        cwd=plugin.path,
        capture_output=True,
        text=True,
    )
    return finished.stderr.strip() if finished.returncode != 0 else None


def _pinned_packages(plugin: PluginFolder) -> int:
    """How many packages requirements.txt pins, the libraries' own dependencies included."""
    pinned = _read(plugin, "requirements.txt") or ""
    return len(re.findall(r"^[A-Za-z0-9][^=\s]*==", pinned, re.MULTILINE))


def _read(plugin: PluginFolder, name: str) -> str | None:
    """A file's text, or None when the plugin has no such file."""
    path = plugin.path / name
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _restore(plugin: PluginFolder, name: str, text: str | None) -> None:
    """A file as it was, including not being there at all."""
    path = plugin.path / name
    if text is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(text, encoding="utf-8")
