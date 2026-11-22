"""What a runtime is given for a plugin: the gateway's address for it, and the thread's key."""

from api.config import get_settings
from modules.agent.plugin_gateway.gateway_key import gateway_key


def given_server(
    plugin_id: str, where: tuple[int, int], launch_key: str
) -> tuple[str, dict[str, str]]:
    workspace_id, thread_id = where
    api = get_settings()
    url = (
        f"http://{api.host}:{api.port}/agent/plugins/workspaces/{workspace_id}"
        f"/threads/{thread_id}/{plugin_id}"
    )
    key = gateway_key(launch_key, workspace_id, thread_id)
    return url, {"Authorization": f"Bearer {key}"}
