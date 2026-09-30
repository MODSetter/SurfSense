"""What the app hands a run in its environment, so verbs need no ids from the author."""

import os


def api_url() -> str:
    """Where the app's API answers for this run; the port changes every launch."""
    return _required(
        "SURFSENSE_PLUGIN_API_URL",
        "so the plugin cannot reach SurfSense. The app sets it on every run; to run"
        " a plugin yourself, use python -m surfsense_plugin_sdk.harness, which finds a"
        " running app or takes --api-url",
    )


def workspace_id() -> str:
    """The workspace the run was started in, where every verb writes."""
    return _required(
        "SURFSENSE_PLUGIN_WORKSPACE_ID",
        "so the plugin does not know which workspace it runs in. The app sets it"
        " on every run, and so does python -m surfsense_plugin_sdk.harness",
    )


def run_id() -> int | None:
    """None under the harness, which starts no run in the app."""
    value = os.environ.get("SURFSENSE_PLUGIN_RUN_ID")
    return int(value) if value else None


def _required(variable: str, consequence: str) -> str:
    """A variable the app always sets, refused by name with what it breaks."""
    value = os.environ.get(variable)
    if not value:
        raise RuntimeError(f"{variable} is not set, {consequence}")
    return value
