import enum
import json
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from modules.plugins.bundles.models import PluginRun
from modules.plugins.bundles.plugin_interpreter import plugin_python
from modules.plugins.bundles.runner.log_tail import LogTail
from modules.plugins.bundles.runner.plugin_environment import plugin_environment
from modules.plugins.bundles.runner.stop_process_tree import stop_process_tree
from shared.config import get_storage_settings

# How often a running plugin is checked for its timeout and for a cancel.
CHECK_SECONDS = 1

# How long the output is still read once the plugin has exited. A process it
# left behind can hold the output open for good.
LAST_OUTPUT_SECONDS = 2


class Stopped(enum.StrEnum):
    """Why the app ended a plugin that had not ended itself."""

    TIMEOUT = "timeout"
    CANCEL = "cancel"


@dataclass(frozen=True)
class EndedProcess:
    """How a plugin's process ended, and the last of what it printed."""

    exit_code: int
    log_tail: str
    stopped: Stopped | None


def run_plugin_process(
    run: PluginRun, timeout_seconds: int, cancel_requested: Callable[[], bool]
) -> EndedProcess:
    """Start the run's plugin with the protocol's command and watch it until it ends."""
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
        log_tail = LogTail()
        reader = threading.Thread(
            target=log_tail.read_from, args=(process.stdout,), daemon=True
        )
        reader.start()
        stopped = _watch(process, timeout_seconds, cancel_requested)
        exit_code = process.wait()
        reader.join(timeout=LAST_OUTPUT_SECONDS)
        return EndedProcess(exit_code, log_tail.text(), stopped)


def _watch(
    process: subprocess.Popen[bytes],
    timeout_seconds: int,
    cancel_requested: Callable[[], bool],
) -> Stopped | None:
    """Wait for the plugin to exit, stopping it on its timeout or on a cancel."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            process.wait(timeout=CHECK_SECONDS)
            return None
        except subprocess.TimeoutExpired:
            pass
        if time.monotonic() >= deadline:
            stop_process_tree(process.pid)
            return Stopped.TIMEOUT
        if cancel_requested():
            stop_process_tree(process.pid)
            return Stopped.CANCEL
