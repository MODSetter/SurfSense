"""A link the agent's web tools take: http(s) with a host, refused before any network otherwise."""

from urllib.parse import urlsplit

from modules.agent.tool_endpoint.tool import ToolCallError

# As long as Add from the web takes.
MAX_URL = 2048


def web_link(given: object) -> str:
    url = str(given or "").strip()
    parts = urlsplit(url)
    if (
        len(url) > MAX_URL
        or parts.scheme not in ("http", "https")
        or not parts.hostname
    ):
        raise ToolCallError("url is a web address starting with https:// or http://.")
    return url
