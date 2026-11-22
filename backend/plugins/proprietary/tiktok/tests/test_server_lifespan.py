"""The plugin's lifespan warms the headless browser for free, behind a switch (no browser)."""

from __future__ import annotations

import asyncio
import importlib
from types import ModuleType

import pytest

from proprietary.tiktok.session import listing


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    # server.py builds its license check at import, which needs a Keygen account.
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", "test-account")
    return importlib.import_module("proprietary.tiktok.server")


@pytest.mark.parametrize(("flag", "warmed"), [("1", 1), ("0", 0)])
async def test_the_lifespan_warms_the_browser_unless_switched_off(
    server: ModuleType, monkeypatch, flag: str, warmed: int
):
    calls: list[int] = []

    async def warm() -> None:
        calls.append(1)

    monkeypatch.setattr(server, "warm_browser", warm)
    monkeypatch.setenv("TIKTOK_WARM_BROWSER", flag)

    async with server.lifespan():
        await asyncio.sleep(0)

    assert len(calls) == warmed


async def test_a_failed_warm_up_leaves_the_plugin_serving(
    server: ModuleType, monkeypatch, caplog
):
    async def warm() -> None:
        raise RuntimeError("no chromium here")

    monkeypatch.setattr(server, "warm_browser", warm)
    monkeypatch.setenv("TIKTOK_WARM_BROWSER", "1")

    async with server.lifespan():
        await asyncio.sleep(0)

    assert "browser warm-up failed" in caplog.text


async def test_the_warm_up_launches_the_headless_profile_with_no_page(monkeypatch):
    profiles = []

    async def warm(profile) -> None:
        profiles.append(profile)

    monkeypatch.setattr(listing.browser_pool, "warm", warm)

    await listing.warm_browser()

    (profile,) = profiles
    assert profile.headless is True
    assert profile == listing._launch(headless=True)[0]
