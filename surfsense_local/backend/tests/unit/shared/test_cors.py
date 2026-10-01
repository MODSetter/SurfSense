import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import add_cors

pytestmark = pytest.mark.unit


def _client(cors_origins: str | None) -> TestClient:
    app = FastAPI()
    app.get("/ping")(lambda: {"ok": True})
    settings = (
        Settings() if cors_origins is None else Settings(cors_origins=cors_origins)
    )
    add_cors(app, settings)
    return TestClient(app)


def test_unset_answers_cross_origin_requests() -> None:
    """Desktop app: the window loads from file:// and must keep reaching the sidecar."""
    response = _client(None).get("/ping", headers={"Origin": "null"})
    assert response.headers.get("access-control-allow-origin") == "*"


def test_empty_sends_no_cors_headers() -> None:
    """Docker image: same-origin behind the proxy, so cross-origin access is off."""
    response = _client("").get("/ping", headers={"Origin": "https://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_listed_origin_is_allowed_and_others_are_not() -> None:
    """A named list is honoured as-is, not widened to `*`."""
    client = _client("https://app.example")
    allowed = client.get("/ping", headers={"Origin": "https://app.example"})
    denied = client.get("/ping", headers={"Origin": "https://other.example"})
    assert allowed.headers.get("access-control-allow-origin") == "https://app.example"
    assert "access-control-allow-origin" not in denied.headers
