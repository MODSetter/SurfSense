"""Ask ggml what this machine has, from a process that can afford to die.

Three reasons the probe is not run in the API process, all of them measured:

- `ggml_backend_load_all` scans the **running executable's own directory**, so
  the child is spawned with its working directory set to the library folder.
  In process that meant a global `chdir` under a lock, in a server that is
  serving other requests.
- On Metal the first device query compiles twenty shader libraries, once, at 19
  seconds. In a child that is 19 seconds of a process nobody is waiting on.
- A GPU driver that faults takes its process with it. A child is a probe that
  failed; the API process is the application.

Unsloth runs its own Vulkan probe this way and for the first of those reasons.

The in-process path stays as a fallback, because a child that cannot be spawned
at all is still a question worth answering.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

from modules.llm.hardware.device_lines import decode_lines
from modules.llm.hardware.devices import Device
from modules.llm.hardware.probe import probe_devices_in_process

logger = logging.getLogger(__name__)

# The flag the frozen binary dispatches on, mirroring the one the retrieval
# check already uses. A frozen build has no interpreter to run `-m` with, so it
# re-executes itself.
PROBE_FLAG = "--probe-devices"

# Generous, because it is bounding the Metal shader compile rather than the
# probe: 19 seconds measured cold, and a machine slower than that still deserves
# an answer rather than a fallback.
DEFAULT_TIMEOUT_SECONDS = 90.0

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def probe_devices(
    library_dir: Path, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
) -> list[Device]:
    """Every device ggml can see, in ggml's own preference order.

    An empty list means ggml found nothing, which is not the same as the machine
    having nothing. `gpu_status` is what tells those apart.

    Raises `OSError` when there is no staged runtime to probe, which is the
    contract the catalog relies on to render without one.
    """
    if not library_dir.is_dir():
        raise OSError(f"no staged runtime at {library_dir}")

    # Resolved before it is handed over, because the child is started *in* this
    # directory. A relative path would be read again against the new working
    # directory, find nothing, and fall back in process: the exact behaviour
    # this module exists to avoid, and silent, because the fallback answers.
    library_dir = library_dir.resolve()

    try:
        finished = subprocess.run(
            _command(library_dir),
            cwd=library_dir,
            env=_environment(),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("device probe could not run as a child process: %s", error)
        return probe_devices_in_process(library_dir)

    if finished.returncode != 0:
        logger.warning(
            "device probe exited %s, falling back in process: %s",
            finished.returncode,
            finished.stderr.strip()[-500:],
        )
        return probe_devices_in_process(library_dir)

    return decode_lines(finished.stdout)


def _command(library_dir: Path) -> list[str]:
    """How to start the child, frozen or not.

    Frozen there is no interpreter and no importable package, so the binary
    re-executes itself behind a flag its entry point dispatches on.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, PROBE_FLAG, str(library_dir)]
    return [
        sys.executable,
        "-m",
        "modules.llm.hardware.probe_script",
        str(library_dir),
    ]


def _environment() -> dict[str, str]:
    """The child's environment, with this backend importable.

    The working directory is the library folder, which is what ggml's scan
    needs and what `-m` would otherwise resolve imports against.
    """
    environment = dict(os.environ)
    if getattr(sys, "frozen", False):
        return environment

    existing = environment.get("PYTHONPATH", "")
    root = str(_BACKEND_ROOT)
    if root not in existing.split(os.pathsep):
        environment["PYTHONPATH"] = (
            f"{root}{os.pathsep}{existing}" if existing else root
        )
    return environment
