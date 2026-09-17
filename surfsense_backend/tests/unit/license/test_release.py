"""GitHub tag-release installers, the same payload the /downloads page uses."""

from __future__ import annotations

import httpx
import pytest

from app.license.release import APP_RELEASE_TAG, get_release_assets, parse_assets

pytestmark = pytest.mark.unit

_EXE = (
    "https://github.com/MODSetter/SurfSense/releases/download/"
    f"{APP_RELEASE_TAG}/SurfSense-Setup-2.0.0.exe"
)
_DMG = (
    "https://github.com/MODSetter/SurfSense/releases/download/"
    f"{APP_RELEASE_TAG}/SurfSense-2.0.0-arm64.dmg"
)
_YML = (
    "https://github.com/MODSetter/SurfSense/releases/download/"
    f"{APP_RELEASE_TAG}/latest.yml"
)


def test_parse_assets_keeps_installers_in_grid_order_and_drops_updater_files():
    assets = parse_assets(
        {
            "assets": [
                {"name": "latest.yml", "browser_download_url": _YML},
                {
                    "name": "SurfSense-2.0.0-arm64.dmg",
                    "browser_download_url": _DMG,
                },
                {
                    "name": "SurfSense-Setup-2.0.0.exe",
                    "browser_download_url": _EXE,
                },
            ]
        }
    )

    assert [(a.name, a.url) for a in assets] == [
        ("SurfSense-Setup-2.0.0.exe", _EXE),
        ("SurfSense-2.0.0-arm64.dmg", _DMG),
    ]


def test_parse_assets_is_empty_on_junk():
    assert parse_assets(None) == ()
    assert parse_assets({"assets": "nope"}) == ()


async def test_get_release_assets_reads_the_tagged_release_not_latest():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "assets": [
                    {
                        "name": "SurfSense-Setup-2.0.0.exe",
                        "browser_download_url": _EXE,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assets = await get_release_assets(client=client)

    assert seen[0].url.path.endswith(f"/releases/tags/{APP_RELEASE_TAG}")
    assert "latest" not in str(seen[0].url)
    assert assets[0].url == _EXE


async def test_a_missing_tag_yields_no_installers_rather_than_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await get_release_assets(client=client) == ()
