import os


class ApiNotRunningError(RuntimeError):
    """No API address was handed to this process, so it cannot reach a model."""


def api_url() -> str:
    """The app's API, at the address Electron hands every Python sidecar."""
    port = os.environ.get("SURFSENSE_LOCAL_PORT")
    if not port:
        raise ApiNotRunningError("the app's API is not running")
    host = os.environ.get("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    return f"http://{host}:{port}"
