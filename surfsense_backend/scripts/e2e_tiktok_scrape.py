"""Manual functional e2e for the TikTok scraper (blob + browser-listing seams).

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/e2e_tiktok_scrape.py

What it exercises (everything REAL — live network, live proxy, live browser):

  Stage 1 — proxy egress proof (informational).
  Stage 2 — profile listing via the stealth browser (soft-blocked by TikTok;
            expected empty until a stronger anti-detection path exists).
  Stage 3 — blob video path over HTTP (URL taken from a captured hashtag struct).
  Stage 4 — hashtag listing via the stealth browser (captures item_list XHRs).
  Stage 5 — full scrape_tiktok() pipeline on a hashtag.

On success it writes raw itemStructs under tests/fixtures/tiktok/ so the parser
suites can pin against real-shaped data without network.

This is NOT a pytest test (it needs a live stack + proxy + a real browser). It is
the manual counterpart to the unit suites and the truth check for
``session/listing.py``, which is otherwise unverified.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import load_dotenv

# --- bootstrap: load .env and put the backend root on sys.path before app.* ---
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))
for _candidate in (_BACKEND_ROOT / ".env", _BACKEND_ROOT.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break

_FIXTURES = _BACKEND_ROOT / "tests" / "fixtures" / "tiktok"

# Evergreen public targets: a regular high-volume creator and a broad hashtag.
_PROFILE = "nasa"
_HASHTAG = "food"
_COUNT = 5


def _mask(url: str | None) -> str:
    if not url:
        return "<none>"
    p = urlsplit(url)
    creds = "***@" if p.username else ""
    port = f":{p.port}" if p.port else ""
    return f"{p.scheme}://{creds}{p.hostname or '?'}{port}"


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{f' — {detail}' if detail else ''}")
    return ok


def _dump_fixture(name: str, data: Any) -> None:
    _FIXTURES.mkdir(parents=True, exist_ok=True)
    path = _FIXTURES / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [fixture] wrote {path.relative_to(_BACKEND_ROOT)}")


def _url_from_struct(struct: dict[str, Any]) -> str | None:
    """Build a canonical video URL from a captured itemStruct."""
    author = (struct.get("author") or {}).get("uniqueId")
    vid = struct.get("id")
    return f"https://www.tiktok.com/@{author}/video/{vid}" if author and vid else None


async def stage_proxy() -> bool:
    _hr("STAGE 1 — proxy egress (informational)")
    from app.utils.proxy import get_active_provider, get_proxy_url, is_pool_backed

    provider = get_active_provider()
    proxy_url = get_proxy_url()
    print(f"  active proxy provider : {provider.name}")
    print(f"  proxy url             : {_mask(proxy_url)}")
    print(f"  pool-backed (rotates) : {is_pool_backed()}")
    if not proxy_url:
        print("  [INFO] no proxy configured — TikTok may block anonymous access")
    return True


async def stage_profile_listing() -> tuple[bool, list[dict[str, Any]]]:
    _hr(f"STAGE 2 — profile listing (browser): @{_PROFILE}")
    from app.proprietary.platforms.tiktok.session import fetch_item_list

    url = f"https://www.tiktok.com/@{_PROFILE}"
    raw = await fetch_item_list(url, _COUNT)
    ok = _check(
        "captured itemStructs from item_list XHRs",
        len(raw) > 0 and isinstance(raw[0], dict) and bool(raw[0].get("id")),
        f"{len(raw)} struct(s)",
    )
    return ok, raw


async def stage_blob_video(video_url: str) -> tuple[bool, dict[str, Any] | None]:
    _hr("STAGE 3 — blob video path (HTTP)")
    print(f"  target: {video_url}")
    from app.proprietary.platforms.tiktok.extraction import (
        extract_rehydration_data,
        video_item_struct,
    )
    from app.proprietary.platforms.tiktok.session import fetch_html

    html = await fetch_html(video_url)
    if not _check("fetched page HTML", bool(html), f"{len(html or '')} chars"):
        return False, None
    data = extract_rehydration_data(html or "")
    if not _check("extracted rehydration blob", data is not None):
        return False, None
    raw = video_item_struct(data or {})
    ok = _check(
        "blob carries the video itemStruct",
        raw is not None and bool(raw.get("id")),
        f"id={None if raw is None else raw.get('id')}",
    )
    if ok and raw is not None:
        _dump_fixture("video_item_struct.json", raw)
    return ok, raw


async def stage_hashtag_listing() -> tuple[bool, list[dict[str, Any]]]:
    _hr(f"STAGE 4 — hashtag listing (browser): #{_HASHTAG}")
    from app.proprietary.platforms.tiktok.session import fetch_item_list

    url = f"https://www.tiktok.com/tag/{_HASHTAG}"
    raw = await fetch_item_list(url, _COUNT)
    ok = _check(
        "captured itemStructs for hashtag",
        len(raw) > 0 and bool(raw[0].get("id")),
        f"{len(raw)} struct(s)",
    )
    if ok:
        _dump_fixture("listing_item.json", raw[0])
    return ok, raw


async def stage_pipeline() -> bool:
    _hr("STAGE 5 — full scrape_tiktok() pipeline")
    from app.proprietary.platforms.tiktok import TikTokScrapeInput, scrape_tiktok

    items = await scrape_tiktok(
        TikTokScrapeInput(hashtags=[_HASHTAG], resultsPerPage=3), limit=3
    )
    ok = _check(
        "pipeline returns normalized video items",
        len(items) > 0
        and bool(items[0].get("id"))
        and bool(items[0].get("webVideoUrl")),
        f"{len(items)} item(s)",
    )
    if items:
        print(f"  sample: {items[0].get('webVideoUrl')} — {items[0].get('text', '')[:60]!r}")
    return ok


async def main() -> int:
    print("TikTok scraper functional e2e — live network + proxy + browser")
    results: dict[str, bool] = {}

    results["Stage 1 proxy"] = await stage_proxy()

    # Hashtag listing is the reliable browser path; use one of its captured
    # structs to build a real video URL for the HTTP blob path.
    ok_tag, tag_structs = await stage_hashtag_listing()
    results["Stage 4 hashtag listing"] = ok_tag

    video_url = _url_from_struct(tag_structs[0]) if tag_structs else None
    if video_url:
        ok_video, _ = await stage_blob_video(video_url)
        results["Stage 3 blob video"] = ok_video
    else:
        print("\n  [SKIP] Stage 3 — no captured struct to build a video URL")

    ok_profile, _ = await stage_profile_listing()
    results["Stage 2 profile listing"] = ok_profile
    results["Stage 5 pipeline"] = await stage_pipeline()

    _hr("SUMMARY")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL/SKIP'} — {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
