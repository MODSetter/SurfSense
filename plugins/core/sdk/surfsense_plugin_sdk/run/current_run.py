"""What the run command was started with, for the accessors and verbs to read."""

from dataclasses import dataclass
from pathlib import Path

from surfsense_plugin_sdk.run.plugin_manifest import PluginManifest


@dataclass(frozen=True)
class CurrentRun:
    """Set once per process, since each run is its own process."""

    plugin_dir: Path
    action: str
    data: Path
    manifest: PluginManifest


_current: CurrentRun | None = None


def start_run(run: CurrentRun) -> None:
    """Records the run before main.py loads, so accessors work at import too."""
    global _current
    _current = run


def current_run() -> CurrentRun:
    """The run this process was started for, or a clear error outside one."""
    if _current is None:
        raise RuntimeError(
            "this works only while a plugin runs, started by the app or by"
            " surfsense-plugins invoke"
        )
    return _current
