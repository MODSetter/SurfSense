"""Manual functional e2e for the TikTok scraper (blob + browser-listing seams).

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/e2e_tiktok_scrape.py

What it exercises (everything REAL — live network, live proxy, live browser):

  Stage 1 — proxy egress proof (informational).
  Stage 2 — profile via the full pipeline: asserts real videos come back
            (fetch_item_list runs headful), degrading to one ErrorItem if not.
  Stage 3 — blob video path over HTTP (URL taken from a captured hashtag struct).
  Stage 4 — hashtag listing via the stealth browser (captures item_list XHRs).
  Stage 5 — full scrape_tiktok() pipeline on a hashtag.
  Stage 6 — search via the full pipeline: same graceful-degrade contract as
            profile (results feed doesn't load for anonymous sessions).
  Stage 7 — comments on a real video URL (served anonymously once the panel
            opens): real comments OR a single honest ErrorItem.
  Stage 8 — user search: the account-discovery XHR that DOES serve anonymous
            headless sessions — asserts real account records come back.
  Stage 9 — trending: the Explore feed of trending videos — asserts real,
            normalized video items come back.

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

# Evergreen public targets: a regular high-volume creator, a broad hashtag, and
# a common search term.
_PROFILE = "nasa"
_HASHTAG = "food"
_SEARCH = "meal prep"
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
    _hr(f"STAGE 2 — profile listing graceful-degrade: @{_PROFILE}")
    from app.proprietary.platforms.tiktok import TikTokScrapeInput, scrape_tiktok

    # fetch_item_list runs headful, so we expect real videos; still accept an
    # ErrorItem (never a silent empty) to keep the graceful-degradation contract.
    items = await scrape_tiktok(
        TikTokScrapeInput(profiles=[_PROFILE], resultsPerPage=_COUNT), limit=_COUNT
    )
    has_video = any(it.get("id") and not it.get("errorCode") for it in items)
    has_error = any(it.get("errorCode") == "no_items" for it in items)
    ok = _check(
        "profile yields videos or a graceful ErrorItem (never silent empty)",
        has_video or has_error,
        f"{len(items)} item(s); video={has_video} error={has_error}",
    )
    return ok, items


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


async def stage_search_listing() -> tuple[bool, list[dict[str, Any]]]:
    _hr(f"STAGE 6 — search listing graceful-degrade: {_SEARCH!r}")
    from app.proprietary.platforms.tiktok import TikTokScrapeInput, scrape_tiktok

    # The search results feed doesn't load for anonymous headless sessions
    # (results XHR never fires on a cold deep-link). Same contract as profile:
    # verify a graceful ErrorItem instead of a silent empty.
    items = await scrape_tiktok(
        TikTokScrapeInput(searchQueries=[_SEARCH], resultsPerPage=_COUNT), limit=_COUNT
    )
    has_video = any(it.get("id") and not it.get("errorCode") for it in items)
    has_error = any(it.get("errorCode") == "no_items" for it in items)
    ok = _check(
        "search yields videos or a graceful ErrorItem (never silent empty)",
        has_video or has_error,
        f"{len(items)} item(s); video={has_video} error={has_error}",
    )
    return ok, items


async def stage_comments(video_url: str) -> tuple[bool, list[dict[str, Any]]]:
    _hr("STAGE 7 — comments graceful-degrade")
    print(f"  target: {video_url}")
    from app.proprietary.platforms.tiktok import scrape_tiktok_comments

    # Comments load over a signed /api/comment/list XHR that TikTok serves to
    # anonymous sessions once the panel opens. Pass if real comments come back
    # OR a graceful ErrorItem (video has none / disabled / withheld).
    items = await scrape_tiktok_comments(
        [video_url], per_video=_COUNT, limit=_COUNT
    )
    has_comment = any(it.get("id") and not it.get("errorCode") for it in items)
    has_error = any(it.get("errorCode") == "no_comments" for it in items)
    ok = _check(
        "comments yield records or a graceful ErrorItem (never silent empty)",
        has_comment or has_error,
        f"{len(items)} item(s); comment={has_comment} error={has_error}",
    )
    return ok, items


async def stage_user_search() -> tuple[bool, list[dict[str, Any]]]:
    _hr(f"STAGE 8 — user search (browser): {_PROFILE!r}")
    from app.proprietary.platforms.tiktok import search_tiktok_users

    # Unlike keyword *video* search, the account-search XHR serves anonymous
    # headless sessions — so this asserts real records, not just degradation.
    items = await search_tiktok_users([_PROFILE], per_query=_COUNT, limit=_COUNT)
    real = [it for it in items if not it.get("errorCode")]
    ok = _check(
        "user search returns account records",
        bool(real) and bool(real[0].get("uniqueId") or real[0].get("name")),
        f"{len(items)} item(s); accounts={len(real)}",
    )
    if real:
        print(f"  sample: @{real[0].get('uniqueId') or real[0].get('name')}")
    return ok, items


async def stage_trending() -> tuple[bool, list[dict[str, Any]]]:
    _hr("STAGE 9 — trending (browser): Explore feed")
    from app.proprietary.platforms.tiktok import scrape_tiktok_trending

    items = await scrape_tiktok_trending(count=_COUNT)
    real = [it for it in items if not it.get("errorCode")]
    ok = _check(
        "trending returns normalized video items",
        bool(real) and bool(real[0].get("id")) and bool(real[0].get("webVideoUrl")),
        f"{len(items)} item(s); videos={len(real)}",
    )
    if real:
        print(f"  sample: {real[0].get('webVideoUrl')} — {real[0].get('text', '')[:60]!r}")
    return ok, items


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
        ok_comments, _ = await stage_comments(video_url)
        results["Stage 7 comments"] = ok_comments
    else:
        print("\n  [SKIP] Stage 3/7 — no captured struct to build a video URL")

    ok_search, _ = await stage_search_listing()
    results["Stage 6 search listing"] = ok_search

    ok_profile, _ = await stage_profile_listing()
    results["Stage 2 profile listing"] = ok_profile
    results["Stage 5 pipeline"] = await stage_pipeline()

    ok_users, _ = await stage_user_search()
    results["Stage 8 user search"] = ok_users
    ok_trending, _ = await stage_trending()
    results["Stage 9 trending"] = ok_trending

    _hr("SUMMARY")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL/SKIP'} — {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
