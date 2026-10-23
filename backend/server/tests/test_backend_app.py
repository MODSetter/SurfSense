"""The backend serves `/health` and every plugin, in one process."""

from pathlib import Path

import httpx2

from host.app import served_plugins
from host.tests.mcp_calls import tool_names
from host.tests.serving import serving
from server.app import backend_app

SAMPLES = Path(__file__).resolve().parents[2] / "plugins/host/tests/sample_plugins"


async def test_the_backend_answers_its_health_check_and_serves_each_plugin() -> None:
    with serving(backend_app(served_plugins(SAMPLES))) as base:
        assert httpx2.get(f"{base}/health").status_code == 200
        assert await tool_names(f"{base}/notes/mcp") == ["search"]
