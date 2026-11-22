"""The backend serves `/health`, every plugin and the license portal, in one process."""

import time
from pathlib import Path

import httpx2
import pytest
from pydantic import BaseModel

from host.app import served_plugins
from host.tests.mcp_calls import tool_names
from host.tests.serving import serving
from license import keygen, token_bucket
from license.portal import license_portal
from license.settings import config
from mailer.settings import config as mail_config
from server.app import backend_app

SAMPLES = Path(__file__).resolve().parents[2] / "plugins/host/tests/sample_plugins"
SITE = "https://www.surfsense.com"
KEY = "KEY-never-echoed-4f0c"


@pytest.fixture
def licensed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The admin token set and mail off, so a resend stops at its 503 before Keygen."""
    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", "token")
    monkeypatch.setattr(config, "NEXT_FRONTEND_URL", SITE)
    monkeypatch.setattr(mail_config, "SMTP_ENABLED", False)


async def test_the_backend_answers_its_health_check_and_serves_each_plugin() -> None:
    with serving(backend_app(served_plugins(SAMPLES))) as base:
        assert httpx2.get(f"{base}/health").status_code == 200
        assert await tool_names(f"{base}/notes/mcp") == ["search"]


def test_the_license_routes_are_served_only_with_the_keygen_admin_token(
    monkeypatch: pytest.MonkeyPatch, licensed: None
) -> None:
    resend = {"email": "buyer@example.com"}
    with serving(backend_app(served_plugins(SAMPLES), license_portal())) as base:
        served = httpx2.post(f"{base}/api/v1/license/resend", json=resend)

    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", None)
    with serving(backend_app(served_plugins(SAMPLES), license_portal())) as base:
        unserved = httpx2.post(f"{base}/api/v1/license/resend", json=resend)

    assert served.status_code == 503
    assert served.json() == {"detail": "License email delivery is not configured."}
    assert unserved.status_code == 404


def test_the_job_pack_route_is_served_only_with_the_keygen_token(
    monkeypatch: pytest.MonkeyPatch, licensed: None
) -> None:
    """Served, a job SurfSense does not sell is refused before Keygen is asked."""

    def no_keygen(client=None):
        raise AssertionError("an unsold job reached Keygen")

    monkeypatch.setattr(keygen, "_http", no_keygen)
    monkeypatch.setattr(config, "REDIS_URL", None)
    asked = {"key": KEY, "entitlement": "JOB_NOT_SOLD", "runners": ["workbook-rows/1"]}
    with serving(backend_app(served_plugins(SAMPLES), license_portal())) as base:
        served = httpx2.post(f"{base}/api/v1/license/job-pack", json=asked)

    monkeypatch.setattr(config, "KEYGEN_API_TOKEN", None)
    with serving(backend_app(served_plugins(SAMPLES), license_portal())) as base:
        unserved = httpx2.post(f"{base}/api/v1/license/job-pack", json=asked)

    assert served.status_code == 422
    assert served.json()["detail"]["code"] == "unknown_job"
    assert unserved.status_code == 404


def test_the_served_portal_forgets_a_callers_counts_an_hour_on_with_no_request_after(
    monkeypatch: pytest.MonkeyPatch, licensed: None
) -> None:
    """Contract 6: the counts are dropped an hour after the caller's last request, even
    when no later request comes to sweep them out."""

    def no_keygen(client=None):
        raise AssertionError("an unsold job reached Keygen")

    clock = [1_800_000_000.0]
    monkeypatch.setattr(token_bucket.time, "time", lambda: clock[0])
    monkeypatch.setattr(token_bucket, "_memory_buckets", {})
    monkeypatch.setattr(token_bucket, "_SWEEP_SECONDS", 0.05)
    monkeypatch.setattr(keygen, "_http", no_keygen)
    monkeypatch.setattr(config, "REDIS_URL", None)
    asked = {"key": KEY, "entitlement": "JOB_NOT_SOLD", "runners": ["workbook-rows/1"]}
    with serving(backend_app(served_plugins(SAMPLES), license_portal())) as base:
        httpx2.post(f"{base}/api/v1/license/job-pack", json=asked)
        counted = len(token_bucket._memory_buckets)
        clock[0] += 3600
        waited = time.monotonic() + 5
        while token_bucket._memory_buckets and time.monotonic() < waited:
            time.sleep(0.02)
        left = len(token_bucket._memory_buckets)

    assert counted == 2
    assert left == 0


def test_a_refused_portal_body_echoes_nothing(licensed: None) -> None:
    """A portal body carries a license key: its 422 describes the body, repeating none of it."""
    with serving(backend_app(served_plugins(SAMPLES), license_portal())) as base:
        refused = [
            httpx2.post(
                f"{base}/api/v1/license/job-pack",
                json={"key": KEY, "entitlement": "JOB_QUESTIONNAIRE"},
            ),
            httpx2.post(f"{base}/api/v1/license/refresh", json={"key": KEY * 100}),
            httpx2.post(
                f"{base}/api/v1/license/refresh",
                content=f'{{"key": "{KEY}"'.encode(),
                headers={"Content-Type": "application/json"},
            ),
        ]

    for reply in refused:
        assert reply.status_code == 422
        assert KEY not in reply.text
        errors = reply.json()["detail"]
        assert errors
        assert all(set(error) == {"type", "loc", "msg"} for error in errors)


def test_a_body_refused_outside_the_portal_keeps_fastapis_answer() -> None:
    class Note(BaseModel):
        text: str

    app = backend_app(served_plugins(SAMPLES))

    @app.post("/note")
    async def note(body: Note) -> dict[str, str]:
        return {"text": body.text}

    with serving(app) as base:
        reply = httpx2.post(f"{base}/note", json={"title": "kept"})

    assert reply.status_code == 422
    assert reply.json()["detail"][0]["input"] == {"title": "kept"}


def test_the_backend_publishes_no_api_description(licensed: None) -> None:
    with serving(backend_app(served_plugins(SAMPLES), license_portal())) as base:
        pages = [
            httpx2.get(f"{base}{path}") for path in ("/docs", "/redoc", "/openapi.json")
        ]

    assert [page.status_code for page in pages] == [404, 404, 404]


def test_the_site_may_read_the_license_routes(licensed: None) -> None:
    """The success page reads the file's name from Content-Disposition."""
    with serving(backend_app(served_plugins(SAMPLES), license_portal())) as base:
        preflight = httpx2.options(
            f"{base}/api/v1/license/trial",
            headers={
                "Origin": SITE,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        download = httpx2.get(f"{base}/api/v1/license/file", headers={"Origin": SITE})

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == SITE
    assert download.headers["access-control-allow-origin"] == SITE
    assert "Content-Disposition" in download.headers["access-control-expose-headers"]
