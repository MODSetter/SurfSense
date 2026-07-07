"""The REST door generator turns registry verbs into typed POST routes (05)."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.capabilities.core.types import Capability
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
    description="Echo the input back for tests.",
    input_schema=_EchoInput,
    output_schema=_EchoOutput,
    executor=_echo_executor,
    billing_unit=None,
)


def _build_app(capabilities, monkeypatch) -> FastAPI:
    """Mount the generated door with auth/workspace/session/rate-limit stubbed."""
    from app.capabilities.core.access import rest
    from app.capabilities.core.access.rate_limit import enforce_capability_rate_limit

    monkeypatch.setattr(rest, "check_workspace_access", _noop_async, raising=True)
    monkeypatch.setattr(rest, "_record_rest_run", _fake_record, raising=True)

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


async def _fake_record(**kwargs) -> str:
    """Stand-in for the DB-backed recorder so unit tests never touch a database."""
    return "test-run-id"


async def _allow() -> None:
    return None


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_verb_is_exposed_as_typed_post_route(monkeypatch):
    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/test/echo",
            json={"value": "hi"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"echo": "hi"}
    assert resp.headers["X-Run-Id"] == "run_test-run-id"


@pytest.mark.asyncio
async def test_input_is_validated_against_the_verb_schema(monkeypatch):
    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/test/echo",
            json={"wrong": "field"},
        )
    assert resp.status_code == 422


def test_registered_verbs_appear_on_rest():
    """A verb in the registry shows up as a route with no per-verb wiring."""
    import app.capabilities.web  # noqa: F401  (registers web.* at import)
    from app.capabilities.core.access import rest

    router = rest.build_capabilities_router()
    paths = {route.path for route in router.routes}
    assert "/workspaces/{workspace_id}/scrapers/web/crawl" in paths


@pytest.mark.asyncio
async def test_capabilities_endpoint_lists_verbs_with_input_schema(monkeypatch):
    """The playground reads verb identity + input JSON schema from one GET."""
    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.get("/api/v1/workspaces/7/scrapers/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    entry = body[0]
    assert entry["name"] == "test.echo"
    assert entry["description"] == "Echo the input back for tests."
    # The schemas are the pydantic models' JSON schemas: the form renders the
    # input schema, the API reference docs render both.
    assert "value" in entry["input_schema"]["properties"]
    assert "properties" in entry["output_schema"]


@pytest.mark.asyncio
async def test_capabilities_endpoint_exposes_live_pricing(monkeypatch):
    """Billed verbs report their per-item rate; free verbs report an empty list."""
    from app.capabilities.core.types import BillingUnit
    from app.config import config

    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "YOUTUBE_MICROS_PER_VIDEO", 2500)

    billed = Capability(
        name="test.billed",
        description="Billed verb for tests.",
        input_schema=_EchoInput,
        output_schema=_EchoOutput,
        executor=_echo_executor,
        billing_unit=BillingUnit.YOUTUBE_VIDEO,
    )

    app = _build_app([_ECHO, billed], monkeypatch)
    async with _client(app) as client:
        resp = await client.get("/api/v1/workspaces/7/scrapers/capabilities")
    assert resp.status_code == 200
    by_name = {entry["name"]: entry for entry in resp.json()}
    assert by_name["test.echo"]["pricing"] == []
    assert by_name["test.billed"]["pricing"] == [
        {"unit": "video", "micros_per_unit": 2500}
    ]

    # Rates are read live: a config retune shows up without a router rebuild.
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", False)
    async with _client(app) as client:
        resp = await client.get("/api/v1/workspaces/7/scrapers/capabilities")
    assert resp.json()[1]["pricing"] == []


@pytest.mark.asyncio
async def test_over_budget_is_blocked_before_the_executor(monkeypatch):
    from app.capabilities.core.access import rest
    from app.services.web_crawl_credit_service import InsufficientCreditsError

    async def _raise(*args, **kwargs):
        raise InsufficientCreditsError(
            message="over budget", balance_micros=0, required_micros=1000
        )

    monkeypatch.setattr(rest, "gate_capability", _raise, raising=True)

    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/test/echo",
            json={"value": "hi"},
        )
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_rate_limit_blocks_the_workspace(monkeypatch):
    """The generated route enforces the per-workspace limit (429)."""
    from app.capabilities.core.access import rate_limit, rest

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
            "/api/v1/workspaces/7/scrapers/test/echo",
            json={"value": "hi"},
        )
    assert resp.status_code == 429


def _register_surfsense_handler(app: FastAPI) -> None:
    """Minimal stand-in for the app's global SurfSenseError handler."""
    from starlette.responses import JSONResponse

    from app.exceptions import SurfSenseError

    async def _handler(_request, exc: SurfSenseError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    app.add_exception_handler(SurfSenseError, _handler)


@pytest.mark.asyncio
async def test_executor_fault_becomes_502(monkeypatch):
    """Any non-SurfSense executor error is surfaced as a clean 502, not a 500."""

    async def _boom(_payload: _EchoInput) -> _EchoOutput:
        raise RuntimeError("upstream provider exploded")

    boom = Capability(
        name="test.boom",
        description="Always fails for tests.",
        input_schema=_EchoInput,
        output_schema=_EchoOutput,
        executor=_boom,
        billing_unit=None,
    )

    app = _build_app([boom], monkeypatch)
    _register_surfsense_handler(app)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/test/boom",
            json={"value": "hi"},
        )
    assert resp.status_code == 502
    assert resp.json()["code"] == "CAPABILITY_UPSTREAM_ERROR"


@pytest.mark.asyncio
async def test_surfsense_error_passes_through(monkeypatch):
    """Intentional, status-carrying errors (e.g. a 403 wall) are not remapped."""
    from app.exceptions import ForbiddenError

    async def _forbidden(_payload: _EchoInput) -> _EchoOutput:
        raise ForbiddenError("sign in required", code="GOOGLE_SIGNIN_REQUIRED")

    forbidden = Capability(
        name="test.forbidden",
        description="Raises a domain 403 for tests.",
        input_schema=_EchoInput,
        output_schema=_EchoOutput,
        executor=_forbidden,
        billing_unit=None,
    )

    app = _build_app([forbidden], monkeypatch)
    _register_surfsense_handler(app)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/test/forbidden",
            json={"value": "hi"},
        )
    assert resp.status_code == 403
    assert resp.json()["code"] == "GOOGLE_SIGNIN_REQUIRED"


def _fake_run_row(**overrides):
    from datetime import UTC, datetime
    from uuid import uuid4

    defaults = {
        "id": uuid4(),
        "capability": "test.echo",
        "origin": "api",
        "status": "success",
        "item_count": 2,
        "char_count": 42,
        "duration_ms": 10,
        "cost_micros": None,
        "error": None,
        "created_at": datetime.now(UTC),
        "thread_id": None,
        "input": {"value": "hi"},
        "output_text": '{"echo": "hi"}',
        "progress": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _build_app_with_rows(monkeypatch, rows):
    """App whose fake session answers select() with the given Run-like rows."""
    from app.capabilities.core.access import rest

    monkeypatch.setattr(rest, "check_workspace_access", _noop_async, raising=True)

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return rows

        def scalar_one_or_none(self):
            return rows[0] if rows else None

    class _Session:
        async def execute(self, stmt):
            return _Result()

    app = FastAPI()
    app.include_router(rest.build_capabilities_router([]), prefix="/api/v1")
    app.dependency_overrides[get_auth_context] = lambda: SimpleNamespace(user=None)

    async def _session():
        yield _Session()

    app.dependency_overrides[get_async_session] = _session
    return app


@pytest.mark.asyncio
async def test_runs_list_returns_metadata_without_output(monkeypatch):
    row = _fake_run_row()
    app = _build_app_with_rows(monkeypatch, [row])
    async with _client(app) as client:
        resp = await client.get("/api/v1/workspaces/7/scrapers/runs")
    assert resp.status_code == 200
    [item] = resp.json()
    assert item["id"] == f"run_{row.id}"
    assert item["capability"] == "test.echo"
    assert "output_text" not in item  # list is metadata-only


@pytest.mark.asyncio
async def test_run_detail_includes_output(monkeypatch):
    row = _fake_run_row()
    app = _build_app_with_rows(monkeypatch, [row])
    async with _client(app) as client:
        resp = await client.get(f"/api/v1/workspaces/7/scrapers/runs/run_{row.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["output_text"] == '{"echo": "hi"}'
    assert body["input"] == {"value": "hi"}


@pytest.mark.asyncio
async def test_run_detail_404s(monkeypatch):
    app = _build_app_with_rows(monkeypatch, [])
    async with _client(app) as client:
        missing = await client.get(
            "/api/v1/workspaces/7/scrapers/runs/run_00000000-0000-0000-0000-000000000000"
        )
        malformed = await client.get("/api/v1/workspaces/7/scrapers/runs/garbage")
    assert missing.status_code == 404
    assert malformed.status_code == 404  # bad UUID must not become a 500


@pytest.mark.asyncio
async def test_success_charges_once(monkeypatch):
    from unittest.mock import AsyncMock

    from app.capabilities.core.access import rest

    charge = AsyncMock()
    monkeypatch.setattr(rest, "charge_capability", charge, raising=True)

    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/test/echo",
            json={"value": "hi"},
        )
    assert resp.status_code == 200
    charge.assert_awaited_once()
    (output, unit, ctx), _ = charge.call_args
    assert isinstance(output, _EchoOutput)
    assert unit is None
    assert ctx.workspace_id == 7


@pytest.mark.asyncio
async def test_async_mode_returns_202_and_pending_run(monkeypatch):
    """``?mode=async`` inserts a pending run and returns its id without blocking."""
    from unittest.mock import AsyncMock

    from app.capabilities.core.access import rest

    monkeypatch.setattr(
        rest, "create_pending_run", AsyncMock(return_value="async-id"), raising=True
    )
    # Don't actually run the scrape in the background during this unit test.
    monkeypatch.setattr(rest, "_execute_async_run", AsyncMock(), raising=True)

    app = _build_app([_ECHO], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/test/echo?mode=async",
            json={"value": "hi"},
        )
    assert resp.status_code == 202
    assert resp.json() == {"run_id": "run_async-id", "status": "running"}


@pytest.mark.asyncio
async def test_run_events_replays_buffer_then_finishes(monkeypatch):
    """The SSE endpoint replays buffered events and closes on ``run.finished``."""
    from app.capabilities.core.events import run_event_bus

    row = _fake_run_row(status="running")
    raw = str(row.id)
    run_event_bus.publish(
        raw, {"type": "run.progress", "phase": "scraping", "current": 1}
    )
    run_event_bus.publish(
        raw, {"type": "run.finished", "status": "success", "item_count": 2}
    )

    app = _build_app_with_rows(monkeypatch, [row])
    try:
        async with _client(app) as client:
            resp = await client.get(
                f"/api/v1/workspaces/7/scrapers/runs/run_{raw}/events"
            )
        assert resp.status_code == 200
        body = resp.text
        assert '"type": "run.progress"' in body
        assert '"type": "run.finished"' in body
        assert '"status": "success"' in body
    finally:
        run_event_bus.close(raw)


@pytest.mark.asyncio
async def test_cancel_finalizes_running_run(monkeypatch):
    """Cancel signals the task, finalizes as ``cancelled``, and emits a terminal."""
    import asyncio
    from unittest.mock import AsyncMock

    from app.capabilities.core.access import rest
    from app.capabilities.core.events import run_event_bus

    finalize = AsyncMock(return_value=True)
    monkeypatch.setattr(rest, "finalize_run", finalize, raising=True)

    row = _fake_run_row(status="running")
    raw = str(row.id)
    task = asyncio.create_task(asyncio.sleep(60))
    run_event_bus.register_task(raw, task)

    app = _build_app_with_rows(monkeypatch, [row])
    try:
        async with _client(app) as client:
            resp = await client.post(
                f"/api/v1/workspaces/7/scrapers/runs/run_{raw}/cancel"
            )
        assert resp.status_code == 200
        assert resp.json() == {"run_id": f"run_{raw}", "status": "cancelled"}
        finalize.assert_awaited_once()
        assert finalize.await_args.kwargs["status"] == "cancelled"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        run_event_bus.close(raw)


@pytest.mark.asyncio
async def test_cancel_conflicts_when_not_running(monkeypatch):
    """Cancelling a terminal run is a 409, not a silent overwrite."""
    row = _fake_run_row(status="success")
    app = _build_app_with_rows(monkeypatch, [row])
    async with _client(app) as client:
        resp = await client.post(
            f"/api/v1/workspaces/7/scrapers/runs/run_{row.id}/cancel"
        )
    assert resp.status_code == 409


def test_emit_progress_is_a_noop_without_context():
    """Scraper code can call ``emit_progress`` freely; unset context = no-op."""
    from app.capabilities.core.progress import emit_progress, progress_scope

    # No active reporter -> returns without raising, records nothing.
    emit_progress("phase", "message", current=1, total=2, unit="item")

    # Inside a scope, coarse events are buffered for persistence.
    with progress_scope() as reporter:
        emit_progress("starting", "go")
        emit_progress("done", current=5, unit="item")
    assert len(reporter.coarse) == 2
    assert reporter.coarse[0]["phase"] == "starting"
