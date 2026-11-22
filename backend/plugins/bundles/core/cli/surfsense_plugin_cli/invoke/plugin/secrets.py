"""The plugin's declared secrets, handed over only in the run's environment.

Never a flag, so a secret stays out of shell history, and never a file.
"""

import getpass
import os
import sys

from surfsense_plugin_manifest import Manifest


def secrets_for(manifest: Manifest) -> dict[str, str]:
    """One variable per declared secret: the author's own, else asked for."""
    found: dict[str, str] = {}
    for declared in manifest.secrets:
        variable = f"SURFSENSE_PLUGIN_SECRET_{declared.name.upper()}"
        found[variable] = os.environ.get(variable) or _asked_for(declared.title)
    return found


def _asked_for(title: str) -> str:
    """Typed without echo at a terminal; read as a line when piped, for scripts."""
    if sys.stdin.isatty():
        return getpass.getpass(f"{title}: ")
    sys.stderr.write(f"{title}: ")
    sys.stderr.flush()
    return sys.stdin.readline().rstrip("\n")
