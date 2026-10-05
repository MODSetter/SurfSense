import os
import sys
from pathlib import Path

from worker.document_script.run_folder import IMAGES_FOLDER

# What a script may see of the worker's environment: enough for Python and the
# OS to start. Never the rest, which holds SURFSENSE_LOCAL_SECRET and model keys.
_FROM_THE_SYSTEM = (
    ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
    if sys.platform == "win32"
    else ("PATH", "HOME", "LANG")
)


def child_environment(
    folder: Path, output_name: str, template_name: str | None = None
) -> dict[str, str]:
    """Everything a script's process gets, built from scratch: the OS basics and
    the script contract. TEMPLATE_PATH only when the run has a template."""
    allowed = {
        name: os.environ[name] for name in _FROM_THE_SYSTEM if name in os.environ
    }
    template = (
        {} if template_name is None else {"TEMPLATE_PATH": str(folder / template_name)}
    )
    return (
        allowed
        | template
        | {
            "OUTPUT_PATH": str(folder / output_name),
            "IMAGES_DIR": str(folder / IMAGES_FOLDER),
            # No display exists for a script, and its font cache goes with the folder.
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(folder / ".mpl"),
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
