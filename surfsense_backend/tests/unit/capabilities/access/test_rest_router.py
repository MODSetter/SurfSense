"""The REST door generator turns registry verbs into typed POST routes (05)."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.capabilities.types import Capability
from app.db import get_async_session
from app.users import get_auth_context


class _EchoInput(BaseModel):
    value: str


class _EchoOutput(BaseModel):
    echo: str


async def _echo_executor(payload: _EchoInput) -> _EchoOutput:
    return _EchoOutput(echo=payload.value)


_ECHO = Capability(
    name="test.echo",
    input_schema=_EchoInput,
    output_schema=_EchoOutput,
    executor=_echo_executor,
    billing_unit=None,
)


def _build_app(capabilities, monkeypatch) -> FastAPI:
    """Mount the generated door with auth/workspace/session/rate-limit stubbed."""
    from app.capabilities.access import rest
    from app.capabilities.access.rate_limit import enforce_capability_rate_limit

    monkeypatch.setattr(rest, "check_workspace_access", _noop_async, raising=True)

    app = FastAPI()
    app.include_router(rest.build_capabilities_router(capabilities), prefix="/api/v1")
    app.dependency_overrides[get_auth_context] = lambda: SimpleNamespace(user=None)
    app.dependency_overrides[enforce_capability_rate_limit] = _allow

    async def _session():
        yield SimpleNamespace()

    app.dependency_overrides[get_async_session] = _session
    return app


async def _noop_async(*args, **kwargs) -> None:
    return None


async def _allow() -> None:
    return None


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_verb_is_exposed_as_typed_post_route(monkeypatch):
    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/capabilities/test.echo",
            json={"value": "hi"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"echo": "hi"}


@pytest.mark.asyncio
async def test_input_is_validated_against_the_verb_schema(monkeypatch):
    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/capabilities/test.echo",
            json={"wrong": "field"},
        )
    assert resp.status_code == 422


def test_registered_verbs_appear_on_rest():
    """A verb in the registry shows up as a route with no per-verb wiring."""
    import app.capabilities.web  # noqa: F401  (registers web.* at import)
    from app.capabilities.access import rest

    router = rest.build_capabilities_router()
    paths = {route.path for route in router.routes}
    assert "/workspaces/{workspace_id}/capabilities/web.scrape" in paths
    assert "/workspaces/{workspace_id}/capabilities/web.discover" in paths


@pytest.mark.asyncio
async def test_over_budget_is_blocked_before_the_executor(monkeypatch):
    from app.capabilities.access import rest
    from app.services.web_crawl_credit_service import InsufficientCreditsError

    async def _raise(*args, **kwargs):
        raise InsufficientCreditsError(
            message="over budget", balance_micros=0, required_micros=1000
        )

    monkeypatch.setattr(rest, "gate_capability", _raise, raising=True)

    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/capabilities/test.echo",
            json={"value": "hi"},
        )
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_rate_limit_blocks_the_workspace(monkeypatch):
    """The generated route enforces the per-workspace limit (429)."""
    from app.capabilities.access import rate_limit, rest

    monkeypatch.setattr(rest, "check_workspace_access", _noop_async, raising=True)
    monkeypatch.setattr(
        rate_limit,
        "_incr",
        lambda *a, **k: rate_limit.CAPABILITY_RATE_LIMIT_PER_MINUTE + 1,
    )

    app = FastAPI()
    app.include_router(rest.build_capabilities_router([_ECHO]), prefix="/api/v1")
    app.dependency_overrides[get_auth_context] = lambda: SimpleNamespace(user=None)

    async def _session():
        yield SimpleNamespace()

    app.dependency_overrides[get_async_session] = _session

    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/capabilities/test.echo",
            json={"value": "hi"},
        )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_success_charges_once(monkeypatch):
    from unittest.mock import AsyncMock

    from app.capabilities.access import rest

    charge = AsyncMock()
    monkeypatch.setattr(rest, "charge_capability", charge, raising=True)

    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/capabilities/test.echo",
            json={"value": "hi"},
        )
    assert resp.status_code == 200
    charge.assert_awaited_once()
    (output, unit, ctx), _ = charge.call_args
    assert isinstance(output, _EchoOutput)
    assert unit is None
    assert ctx.workspace_id == 7
