import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from modules.plugins.models import PluginRun
from modules.plugins.plugin_interpreter import plugin_python
from modules.plugins.runner.plugin_environment import plugin_environment
from shared.config import get_storage_settings

# The end of the output is what is kept: a plugin explains a failure last.
LOG_TAIL_BYTES = 16 * 1024


@dataclass(frozen=True)
class EndedProcess:
    """How a plugin's process ended, and the last of what it printed."""

    exit_code: int
    log_tail: str


def run_plugin_process(run: PluginRun) -> EndedProcess:
    """Start the run's plugin with the protocol's command and wait for its exit."""
    storage = get_storage_settings()
    folder = storage.plugin_dir(run.plugin_id, run.version)
    with tempfile.TemporaryDirectory(prefix="surfsense-plugin-run-") as own_folder:
        inputs_file = Path(own_folder) / "inputs.json"
        inputs_file.write_text(json.dumps(run.inputs), encoding="utf-8")
        # No new session or process group: quitting the app stops the worker's
        # whole group, and the plugin has to be in it.
        process = subprocess.Popen(
            [
                str(plugin_python()),
                # Blind to the packages installed beside that Python, such as the
                # backend's own in development: the packaged app's has none.
                "-S",
                "-m",
                "surfsense_plugin_sdk.run",
                str(folder),
                run.action,
                "--inputs",
                str(inputs_file),
                "--data",
                str(storage.plugin_data_dir(run.plugin_id)),
            ],
            cwd=folder,
            env=plugin_environment(run),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        log_tail = _tail_of(process.stdout)
        return EndedProcess(process.wait(), log_tail)


def _tail_of(output: IO[bytes]) -> str:
    """Read what the plugin prints until it stops, holding only the last of it."""
    tail = b""
    while chunk := output.read1(LOG_TAIL_BYTES):
        tail = (tail + chunk)[-LOG_TAIL_BYTES:]
    return tail.decode(errors="replace")
