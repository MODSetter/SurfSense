"""The headers SurfSense sends a plugin's server for a thread: its sign-in, and on SurfSense's
plugin host the thread's calls token and a request for text-only results."""

from sqlalchemy.orm import Session

from modules.agent.plugin_tools.thread_calls import CALLS_HEADER, thread_calls_token
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.lists.plugin_host import on_plugin_host
from modules.plugins.remote.sign_in.plugin_headers import sign_in_headers

# Asks SurfSense's plugin host for a call's items in the text alone: a runtime reads
# only the text when there is any, so the structured copy would be sent for nothing.
TEXT_ONLY_HEADER = "x-surfsense-text-only"


def upstream_headers(
    session: Session, plugin: InstalledPlugin, thread_id: int
) -> dict[str, str]:
    headers = sign_in_headers(session, plugin)
    if on_plugin_host(plugin.url):
        headers[TEXT_ONLY_HEADER] = "1"
        headers[CALLS_HEADER] = thread_calls_token(thread_id)
    return headers
