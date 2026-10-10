import os

from modules.plugins.bundles.models import PluginRun
from modules.plugins.bundles.plugin_interpreter import plugin_sdk

# What the protocol lets through from the operating system.
_FROM_THE_SYSTEM = (
    "PATH",
    "HOME",
    "USERPROFILE",
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "APPDATA",
    "LOCALAPPDATA",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
)


def plugin_environment(run: PluginRun) -> dict[str, str]:
    """Everything a plugin's process gets, built from scratch.

    Never a copy of the worker's own: that holds SURFSENSE_LOCAL_SECRET, the
    key to every stored API key, and a child inherits what it is not denied.
    """
    allowed = {
        name: os.environ[name] for name in _FROM_THE_SYSTEM if name in os.environ
    }
    return allowed | _for_python() | _context(run)


def _for_python() -> dict[str, str]:
    """How the interpreter starts: the SDK importable, nothing else leaking in."""
    return {
        "PYTHONPATH": str(plugin_sdk()),
        # `python -m` would put the plugin's folder ahead of the standard library.
        "PYTHONSAFEPATH": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
    }


def _context(run: PluginRun) -> dict[str, str]:
    """Where the run happens, which the SDK reads so a verb needs no ids."""
    return _api_url() | {
        "SURFSENSE_PLUGIN_WORKSPACE_ID": str(run.workspace_id),
        "SURFSENSE_PLUGIN_RUN_ID": str(run.id),
        "SURFSENSE_PLUGIN_ID": run.plugin_id,
    }


def _api_url() -> dict[str, str]:
    """The app's API, at the address Electron gave this worker.

    Left out when the worker was started without one: the SDK then says the
    URL is missing, which a guessed port would turn into a connection error.
    """
    port = os.environ.get("SURFSENSE_LOCAL_PORT")
    if not port:
        return {}
    host = os.environ.get("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    return {"SURFSENSE_PLUGIN_API_URL": f"http://{host}:{port}"}
