"""A secret the plugin declared, which the app hands over only in the environment."""

import os

from surfsense_plugin_sdk.run.current_run import current_run


def secret(name: str) -> str:
    """A secret the plugin declared, as the user entered it in SurfSense."""
    declared = current_run().manifest.get("secrets", [])
    if name not in {s["name"] for s in declared}:
        raise LookupError(
            f'secret "{name}" is not declared: add it to "secrets" in manifest.json'
        )

    variable = f"SURFSENSE_PLUGIN_SECRET_{name.upper()}"
    value = os.environ.get(variable)
    if value is None:
        raise LookupError(
            f'secret "{name}" has no value: set it in the plugin\'s settings in'
            f" SurfSense, or in {variable} when you run surfsense-plugins invoke"
        )
    return value
