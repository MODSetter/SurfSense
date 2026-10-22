"""Plugin calls are counted where the gateway sends them on, and only those that reach the plugin."""

from datetime import UTC, datetime, timedelta

import pytest

from modules.usage_statistics.activity_counts import Activity, read_counts
from tests.integration.agent.test_plugin_gateway import (  # noqa: F401 (fixture)
    Gateway,
    gateway,
)
from tests.mcp_test_server import notes_server, serving

pytestmark = pytest.mark.integration


async def test_a_call_sent_on_is_counted_and_a_blocked_one_is_not(
    gateway: Gateway,  # noqa: F811
) -> None:
    """Listing tools is not a call, and a tool the user blocked never ran."""
    with serving(notes_server().streamable_http_app()) as base:
        await gateway.connect(f"{base}/mcp")
        async with gateway.runtime() as runtime:
            await runtime.call_tool("search", {"query": "a"})
            await gateway.http.put(
                "/plugins/notes/tools/search", json={"enabled": False}
            )
            await runtime.call_tool("search", {"query": "b"})

    counts = read_counts()
    assert counts is not None
    since = datetime.now(UTC) - timedelta(hours=1)
    assert counts.total(Activity.PLUGIN_CALL, since) == 1
