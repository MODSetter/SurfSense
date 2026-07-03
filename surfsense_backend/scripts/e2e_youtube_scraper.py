"""Manual functional e2e for the YouTube scraper (app/proprietary/platforms/youtube).

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/e2e_youtube_scraper.py
    # or: .\\.venv\\Scripts\\python.exe scripts/e2e_youtube_scraper.py

This is NOT a pytest test (it needs live network + optional proxy creds). It:

  Step 0 — validates the keyless InnerTube ``search`` POST works; if it 400s the
      scraper transparently retries with the public web key (proven here).
  Step 1 — scrapes a known video URL (metadata + optional subtitles).
  Step 2 — runs a search query and prints the first few results.
  Step 3 — scrapes a small channel's latest videos.
  Step 4 — dumps trimmed raw ytInitialData / ytInitialPlayerResponse fixtures to
      tests/unit/platforms/youtube/fixtures/ for the offline parser test.
"""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# --- bootstrap: load .env and put the backend root on sys.path before app.* ---
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))
for _candidate in (_BACKEND_ROOT / ".env", _BACKEND_ROOT.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break

from app.proprietary.platforms.youtube import (  # noqa: E402
    YouTubeCommentsInput,
    YouTubeScrapeInput,
    scrape_comments,
    scrape_youtube,
)
from app.proprietary.platforms.youtube.innertube import (  # noqa: E402
    INNERTUBE_PUBLIC_API_KEY,
    INNERTUBE_SEARCH_URL,
    build_innertube_payload,
    fetch_html,
    post_innertube,
)
from app.proprietary.platforms.youtube.parsers import (  # noqa: E402
    extract_yt_initial_data,
    extract_yt_initial_player_response,
)

_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
_SEARCH_TERM = "web scraping tutorials"
_CHANNEL_URL = "https://www.youtube.com/@YouTube"
# A geo-tagged walking tour + a multi-owner collaboration video (long-tail fields).
_LOCATION_VIDEO_URL = "https://www.youtube.com/watch?v=bhJU_fVHMmY"
_COLLAB_VIDEO_URL = "https://www.youtube.com/watch?v=AI2BwwLX_7s"
# MrBeast localizes titles/descriptions into many languages (translation flow).
_TRANSLATED_VIDEO_URL = "https://www.youtube.com/watch?v=iYlODtkyw_I"

_FIXTURE_DIR = _BACKEND_ROOT / "tests" / "unit" / "platforms" / "youtube" / "fixtures"


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{f' — {detail}' if detail else ''}")
    return ok


async def step0_validate_innertube() -> bool:
    _hr("STEP 0 — InnerTube search POST (keyless, then public-key fallback)")
    payload = build_innertube_payload(search_query=_SEARCH_TERM)
    keyless = await post_innertube(INNERTUBE_SEARCH_URL, payload)
    if keyless is not None:
        return _check("keyless search POST", True, "keyless works")
    keyed = await post_innertube(
        INNERTUBE_SEARCH_URL, payload, api_key=INNERTUBE_PUBLIC_API_KEY
    )
    return _check("public-key search POST", keyed is not None, "keyless 400 -> key")


async def step1_video() -> bool:
    _hr("STEP 1 — scrape a known video")
    inp = YouTubeScrapeInput(startUrls=[{"url": _VIDEO_URL}], downloadSubtitles=True)
    items = await scrape_youtube(inp)
    print(json.dumps(items[:1], indent=2)[:2000])
    ok = bool(items) and items[0].get("id") == "dQw4w9WgXcQ"
    return _check("video scraped with id + title", ok and bool(items[0].get("title")))


async def step2_search() -> bool:
    _hr("STEP 2 — search query")
    inp = YouTubeScrapeInput(searchQueries=[_SEARCH_TERM], maxResults=5)
    items = await scrape_youtube(inp)
    for it in items[:5]:
        print(f"  - {it.get('id')} | {it.get('title')}")
    return _check("search returned results", len(items) > 0, f"{len(items)} items")


async def step3_channel() -> bool:
    _hr("STEP 3 — channel latest videos")
    inp = YouTubeScrapeInput(startUrls=[{"url": _CHANNEL_URL}], maxResults=3)
    items = await scrape_youtube(inp)
    for it in items[:3]:
        print(f"  - {it.get('id')} | {it.get('title')}")
    return _check("channel returned videos", len(items) > 0, f"{len(items)} items")


async def step4_dump_fixtures() -> bool:
    _hr("STEP 4 — dump raw fixtures for offline test")
    html = await fetch_html(_VIDEO_URL)
    if not html:
        return _check("fetched video HTML", False)
    initial = extract_yt_initial_data(html)
    player = extract_yt_initial_player_response(html)
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    if player:
        (_FIXTURE_DIR / "video_player_response.json").write_text(
            json.dumps(player), encoding="utf-8"
        )
    if initial:
        (_FIXTURE_DIR / "video_initial_data.json").write_text(
            json.dumps(initial), encoding="utf-8"
        )
    return _check("dumped fixtures", bool(player), f"-> {_FIXTURE_DIR}")


async def step5_comments() -> bool:
    _hr("STEP 5 — comments (+ replies) for a video")
    inp = YouTubeCommentsInput(
        startUrls=[{"url": _VIDEO_URL}], maxComments=6, sortCommentsBy="NEWEST_FIRST"
    )
    items = await scrape_comments(inp)
    for it in items[:6]:
        print(
            f"  - [{it.get('type')}] {it.get('author')} | {it.get('voteCount')} votes"
        )
    ok = bool(items) and all(it.get("cid") and it.get("videoId") for it in items)
    has_reply = any(it.get("type") == "reply" and it.get("replyToCid") for it in items)
    return _check(
        "comments scraped (cid+videoId, reply linkage)",
        ok and has_reply,
        f"{len(items)} items",
    )


async def step6_location_collaborators() -> bool:
    _hr("STEP 6 — long-tail fields: location + collaborators")
    loc_items = await scrape_youtube(
        YouTubeScrapeInput(startUrls=[{"url": _LOCATION_VIDEO_URL}])
    )
    location = loc_items[0].get("location") if loc_items else None
    print(f"  location: {location!r}")
    collab_items = await scrape_youtube(
        YouTubeScrapeInput(startUrls=[{"url": _COLLAB_VIDEO_URL}])
    )
    collaborators = collab_items[0].get("collaborators") if collab_items else None
    print(f"  collaborators: {collaborators}")
    return _check(
        "location + collaborators populated",
        bool(location) and bool(collaborators) and len(collaborators) >= 2,
    )


async def step7_translation() -> bool:
    _hr("STEP 7 — translatedTitle/translatedText (subtitlesLanguage=es)")
    items = await scrape_youtube(
        YouTubeScrapeInput(
            startUrls=[{"url": _TRANSLATED_VIDEO_URL}], subtitlesLanguage="es"
        )
    )
    it = items[0] if items else {}
    print(f"  title          : {it.get('title')}")
    print(f"  translatedTitle: {it.get('translatedTitle')}")
    # A localized video's translated title differs from the canonical English one.
    ok = bool(it.get("translatedTitle")) and it.get("translatedTitle") != it.get(
        "title"
    )
    return _check("translatedTitle differs from original", ok)


async def main() -> int:
    results = []
    results.append(await step0_validate_innertube())
    if not results[-1]:
        print("\nInnerTube unreachable — aborting remaining steps.")
        return 1
    results.append(await step1_video())
    results.append(await step2_search())
    results.append(await step3_channel())
    results.append(await step4_dump_fixtures())
    results.append(await step5_comments())
    results.append(await step6_location_collaborators())
    results.append(await step7_translation())

    _hr("SUMMARY")
    print(f"  {sum(results)}/{len(results)} steps passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
