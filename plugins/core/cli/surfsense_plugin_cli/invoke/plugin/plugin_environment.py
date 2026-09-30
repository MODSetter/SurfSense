"""The environment a plugin runs in, built from scratch as the app's runner builds it.

Nothing else of the author's environment reaches the plugin, so a plugin that
works here does not lean on a variable the app never sets.
"""

import os

from surfsense_plugin_cli.repository import SDK

# What the protocol lets through from the operating system.
FROM_THE_SYSTEM = (
    "PATH",
    "HOME",
    "USERPROFILE",
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "APPDATA",
    "LOCALAPPDATA",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
)

FOR_PYTHON = {
    "PYTHONPATH": str(SDK),
    "PYTHONSAFEPATH": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTHONUTF8": "1",
    "PYTHONUNBUFFERED": "1",
}


def plugin_environment(context: dict[str, str]) -> dict[str, str]:
    """The system's allowed variables, Python's, and the run's own context."""
    allowed = {name: os.environ[name] for name in FROM_THE_SYSTEM if name in os.environ}
    return allowed | FOR_PYTHON | context
