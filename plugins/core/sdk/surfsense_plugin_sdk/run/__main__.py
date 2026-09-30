"""The command the app runs a plugin with, as the protocol fixes it.

python -S -m surfsense_plugin_sdk.run <plugin-dir> <action> --inputs <file> --data <dir>
"""

import argparse
import json
from pathlib import Path

from surfsense_plugin_sdk.run.call_action import call_action


def _run() -> None:
    """Reads the protocol's command line and hands the run to call_action."""
    parser = argparse.ArgumentParser(prog="python -m surfsense_plugin_sdk.run")
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument("action")
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    arguments = parser.parse_args()
    plugin_dir: Path = arguments.plugin_dir
    action_name: str = arguments.action
    inputs_file: Path = arguments.inputs
    data: Path = arguments.data

    given: dict[str, object] = json.loads(inputs_file.read_text(encoding="utf-8"))
    call_action(plugin_dir, action_name, given, data)


_run()
