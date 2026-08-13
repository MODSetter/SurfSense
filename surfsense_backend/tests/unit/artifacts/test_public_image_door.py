"""Guard checks for the anonymous image funnel door.

Verifies the per-IP daily cap returns 429 and, past the request threshold,
the Turnstile requirement returns 403 before any provider call.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.testclient import TestClient

import app.artifacts.generation.access.public as pub
from app.rate_limiter import limiter
from app.services.token_quota_service import TokenQuotaService

pytestmark = pytest.mark.unit


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(pub.config, "NOLOGIN_MODE_ENABLED", True)
    api = FastAPI()
    api.state.limiter = limiter
    api.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    api.add_middleware(SlowAPIMiddleware)
    api.include_router(pub.build_public_artifact_router())
    return TestClient(api)


def test_daily_cap_returns_429(monkeypatch):
    monkeypatch.setattr(pub.config, "TURNSTILE_ENABLED", False)
    monkeypatch.setattr(pub.config, "ANON_IMAGE_DAILY_CAP_PER_IP", 5)

    async def at_cap(ip):
        return 5

    monkeypatch.setattr(TokenQuotaService, "anon_get_image_count", at_cap)

    resp = _client(monkeypatch).post(
        "/api/v1/public/tools/image", json={"prompt": "a cat"}
    )
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "ANON_IMAGE_CAP_REACHED"


def test_captcha_required_past_threshold(monkeypatch):
    monkeypatch.setattr(pub.config, "TURNSTILE_ENABLED", True)
    monkeypatch.setattr(pub.config, "ANON_CAPTCHA_REQUEST_THRESHOLD", 5)

    async def over_threshold(ip):
        return 5

    monkeypatch.setattr(TokenQuotaService, "anon_get_request_count", over_threshold)

    resp = _client(monkeypatch).post(
        "/api/v1/public/tools/image", json={"prompt": "a cat"}
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "CAPTCHA_REQUIRED"
