"""An API that Electron started without opencode serves none of opencode's routes."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from shared.config import get_agent_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

# Each with a body its route accepts, so only a missing route can answer 404.
OPENCODE_ROUTES = [
    ("/agent/model/v1/chat/completions", {"model": "m", "messages": []}),
    (
        "/agent/tools/workspaces/1/threads/1",
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
    ),
    ("/chat/threads/1/permissions/request-1", {"reply": "once"}),
]


@pytest.mark.parametrize(("route", "body"), OPENCODE_ROUTES)
async def test_an_api_without_opencode_has_none_of_its_routes(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, route: str, body: dict
) -> None:
    """While opencode is off, nothing on loopback can reach what only it should call."""
    monkeypatch.setattr(get_agent_settings(), "opencode_url", None)
    monkeypatch.setattr(get_agent_settings(), "opencode_password", None)
    app = create_app()
    app.state.session_factory = create_session_factory(engine)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        reply = await client.post(route, json=body)

    assert reply.status_code == 404
    assert reply.json() == {"detail": "Not Found"}
