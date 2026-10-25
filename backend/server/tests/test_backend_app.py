"""The backend serves `/health`, every plugin and the license portal, in one process."""

from pathlib import Path

import httpx2
import pytest

from host.app import served_plugins
from host.tests.mcp_calls import tool_names
from host.tests.serving import serving
from license.portal import license_portal
from license.settings import config
from mailer.settings import config as mail_config
from server.app import backend_app

SAMPLES = Path(__file__).resolve().parents[2] / "plugins/host/tests/sample_plugins"
SITE = "https://www.surfsense.com"


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
