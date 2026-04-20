"""JWT access/refresh lifetimes follow ACCESS_TOKEN_* / REFRESH_TOKEN_* env (compose maps unified session vars)."""

import importlib
import os

import pytest


@pytest.mark.unit
def test_jwt_lifetime_seconds_from_env(monkeypatch):
    import app.config as cfg_module

    prev_access = os.environ.get("ACCESS_TOKEN_LIFETIME_SECONDS")
    prev_refresh = os.environ.get("REFRESH_TOKEN_LIFETIME_SECONDS")
    try:
        monkeypatch.setenv("ACCESS_TOKEN_LIFETIME_SECONDS", "111")
        monkeypatch.setenv("REFRESH_TOKEN_LIFETIME_SECONDS", "222")
        importlib.reload(cfg_module)
        assert cfg_module.Config.ACCESS_TOKEN_LIFETIME_SECONDS == 111
        assert cfg_module.Config.REFRESH_TOKEN_LIFETIME_SECONDS == 222
    finally:
        if prev_access is not None:
            os.environ["ACCESS_TOKEN_LIFETIME_SECONDS"] = prev_access
        else:
            os.environ.pop("ACCESS_TOKEN_LIFETIME_SECONDS", None)
        if prev_refresh is not None:
            os.environ["REFRESH_TOKEN_LIFETIME_SECONDS"] = prev_refresh
        else:
            os.environ.pop("REFRESH_TOKEN_LIFETIME_SECONDS", None)
        importlib.reload(cfg_module)
