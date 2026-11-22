"""A link the agent's web tools take: http(s) with a host, refused before any network otherwise."""

from urllib.parse import urlsplit

from modules.agent.tool_endpoint.tool import ToolCallError

# As long as Add from the web takes.
MAX_URL = 2048
_NOT_A_WEB_ADDRESS = "url is a web address starting with https:// or http://."


def web_link(given: object) -> str:
    url = str(given or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError as malformed:
        # urlsplit refuses a broken host, such as markdown's "](" left after a link.
        raise ToolCallError(_NOT_A_WEB_ADDRESS) from malformed
    if (
        len(url) > MAX_URL
        or parts.scheme not in ("http", "https")
        or not parts.hostname
    ):
        raise ToolCallError(_NOT_A_WEB_ADDRESS)
    return url
