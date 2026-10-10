import sys
from pathlib import Path

# The repository's root, four folders above this file.
_REPOSITORY = Path(__file__).resolve().parents[4]


def plugin_python() -> Path:
    """The Python program a plugin is started with."""
    # In development: the Python running this worker.
    # The packaged worker is not a Python, so the app will ship one for plugins.
    return Path(sys.executable)


def plugin_sdk() -> Path:
    """The folder a plugin imports `surfsense_plugin_sdk` from."""
    # In development: the repository's copy.
    # The packaged app will ship it beside the plugin's Python.
    return _REPOSITORY / "plugins" / "bundles" / "core" / "sdk"
