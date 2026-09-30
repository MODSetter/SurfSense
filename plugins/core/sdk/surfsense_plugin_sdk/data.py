"""The plugin's own folder, which survives updates and goes on uninstall."""

from pathlib import Path

from surfsense_plugin_sdk.run.current_run import current_run


def data() -> Path:
    """The plugin's own folder: kept across updates, deleted on uninstall."""
    return current_run().data
