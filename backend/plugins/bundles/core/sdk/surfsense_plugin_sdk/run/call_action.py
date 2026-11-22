"""Calls the action the app named, with the inputs the user gave it."""

import sys
from pathlib import Path

from surfsense_plugin_sdk.action import registered_action
from surfsense_plugin_sdk.run.current_run import CurrentRun, start_run
from surfsense_plugin_sdk.run.load_plugin import load_plugin
from surfsense_plugin_sdk.run.plugin_manifest import read_plugin_manifest


def call_action(
    plugin_dir: Path, name: str, given: dict[str, object], data: Path
) -> None:
    """Refuses an undeclared or unmarked action by name, not with a traceback."""
    manifest = read_plugin_manifest(plugin_dir)
    declared = next(
        (
            declared_action
            for declared_action in manifest["actions"]
            if declared_action["name"] == name
        ),
        None,
    )
    if declared is None:
        sys.exit(f'{manifest["id"]} has no action named "{name}"')
    start_run(CurrentRun(plugin_dir, name, data, manifest))

    load_plugin(plugin_dir)
    function = registered_action(name)
    if function is None:
        sys.exit(
            f'manifest.json declares the action "{name}" but main.py has no function'
            f' for it: mark its function with @action("{name}")'
        )

    # An optional input the user left empty is absent from the inputs file.
    # It arrives as None, so the function is never called missing an argument.
    all_inputs_empty = {
        declared_input["name"]: None for declared_input in declared["inputs"]
    }
    function(**(all_inputs_empty | given))
