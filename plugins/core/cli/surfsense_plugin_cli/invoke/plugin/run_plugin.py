"""Starts the plugin with the command the app uses, and waits for how it ends."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from surfsense_plugin_cli.invoke.plugin.plugin_environment import plugin_environment


def run_plugin(
    folder: Path,
    action: str,
    inputs: dict[str, object],
    context: dict[str, str],
) -> int:
    """The plugin's exit code. Its log goes straight to the author's terminal."""
    data = folder / "dev-data"
    data.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="surfsense-invoke-") as run_folder:
        inputs_file = Path(run_folder) / "inputs.json"
        inputs_file.write_text(json.dumps(inputs), encoding="utf-8")
        finished = subprocess.run(
            [
                sys.executable,
                # Blind to the CLI's own packages, as the app's runner is to its own.
                "-S",
                "-m",
                "surfsense_plugin_sdk.run",
                str(folder),
                action,
                "--inputs",
                str(inputs_file),
                "--data",
                str(data),
            ],
            cwd=folder,
            env=plugin_environment(context),
        )
    return finished.returncode
