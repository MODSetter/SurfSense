import pytest

from modules.plugins.installed.server_url import server_url

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("written", "stored"),
    [
        ("https://mcp.notion.com/mcp", "https://mcp.notion.com/mcp"),
        ("HTTPS://MCP.Notion.com/mcp", "https://mcp.notion.com/mcp"),
        ("https://mcp.notion.com/mcp/", "https://mcp.notion.com/mcp"),
        ("https://mcp.notion.com:443/mcp", "https://mcp.notion.com/mcp"),
        ("http://127.0.0.1:80/mcp", "http://127.0.0.1/mcp"),
        ("https://mcp.notion.com:8443/mcp", "https://mcp.notion.com:8443/mcp"),
        ("https://mcp.notion.com/MCP", "https://mcp.notion.com/MCP"),
        ("https://mcp.notion.com/mcp?team=1#top", "https://mcp.notion.com/mcp?team=1"),
        ("  https://mcp.notion.com/mcp  ", "https://mcp.notion.com/mcp"),
    ],
)
def test_one_server_has_one_spelling(written: str, stored: str) -> None:
    """Host and scheme case, default ports, a trailing slash and a fragment never name
    another server; the path and the query can, so they are kept as written."""
    assert server_url(written) == stored
