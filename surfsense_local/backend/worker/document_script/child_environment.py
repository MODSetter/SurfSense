import os
import sys
from pathlib import Path

# What a script may see of the worker's environment: enough for Python and the
# OS to start. Never the rest, which holds SURFSENSE_LOCAL_SECRET and model keys.
_FROM_THE_SYSTEM = (
    ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
    if sys.platform == "win32"
    else ("PATH", "HOME", "LANG")
)


def child_environment(folder: Path, contract: dict[str, str]) -> dict[str, str]:
    """Everything a script's process gets, built from scratch: the OS basics, the
    settings every script runs with, and the paths of its own kind of run."""
    allowed = {
        name: os.environ[name] for name in _FROM_THE_SYSTEM if name in os.environ
    }
    return (
        allowed
        | contract
        | {
            # No display exists for a script, and its font cache goes with the folder.
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(folder / ".mpl"),
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
