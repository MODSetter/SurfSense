"""Auth credential resolution + 401 refresh hook."""

from __future__ import annotations

import httpx
import pytest
import respx

from surfsense_evals.core.auth import (
    CredentialError,
    acquire_token,
    client_with_auth,
)
from surfsense_evals.core.config import Config


def _make_config(**overrides) -> Config:
    base = {
        "surfsense_api_base": "http://test",
        "openrouter_api_key": None,
        "openrouter_base_url": "https://openrouter.ai/api/v1",
        "surfsense_jwt": None,
        "surfsense_refresh_token": None,
        "surfsense_user_email": None,
        "surfsense_user_password": None,
        "data_dir": None,
        "reports_dir": None,
    }
    base.update(overrides)
    # Path objects required by Config; tests don't touch the FS.
    from pathlib import Path

    base["data_dir"] = base["data_dir"] or Path("/tmp/eval_test_data")
    base["reports_dir"] = base["reports_dir"] or Path("/tmp/eval_test_reports")
    return Config(**base)


@pytest.mark.asyncio
async def test_acquire_token_jwt_mode_short_circuits():
    config = _make_config(surfsense_jwt="abc", surfsense_refresh_token="ref")
    bundle = await acquire_token(config)
    assert bundle.access_token == "abc"
    assert bundle.refresh_token == "ref"
    assert bundle.mode == "jwt"


@pytest.mark.asyncio
@respx.mock
async def test_acquire_token_local_mode_posts_desktop_login_json():
    respx.post("http://test/auth/desktop/login").mock(
        return_value=httpx.Response(
            200, json={"access_token": "T", "refresh_token": "R", "token_type": "bearer"}
        )
    )
    config = _make_config(surfsense_user_email="u@example.com", surfsense_user_password="pw")
    bundle = await acquire_token(config)
    assert bundle.access_token == "T"
    assert bundle.refresh_token == "R"
    assert bundle.mode == "local"


@pytest.mark.asyncio
async def test_acquire_token_no_credentials():
    config = _make_config()
    with pytest.raises(CredentialError) as exc:
        await acquire_token(config)
    assert "SURFSENSE_USER_EMAIL" in str(exc.value)
    assert "SURFSENSE_JWT" in str(exc.value)


@pytest.mark.asyncio
@respx.mock
async def test_client_with_auth_refreshes_on_401():
    config = _make_config(surfsense_jwt="old", surfsense_refresh_token="ref")
    bundle = await acquire_token(config)

    respx.post("http://test/auth/jwt/refresh").mock(
        return_value=httpx.Response(200, json={"access_token": "new", "refresh_token": "ref2"})
    )
    # First call returns 401; the retry (post-refresh) returns 200.
    respx.get("http://test/api/v1/searchspaces").mock(
        side_effect=[
            httpx.Response(401, json={"detail": "expired"}),
            httpx.Response(200, json=[]),
        ]
    )

    async with client_with_auth(config, bundle) as client:
        response = await client.get("http://test/api/v1/searchspaces")

    assert response.status_code == 200
    assert bundle.access_token == "new"
    assert bundle.refresh_token == "ref2"
