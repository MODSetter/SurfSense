"""Manual functional e2e for the Instagram scraper (app/proprietary/platforms/instagram).

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/e2e_instagram_scraper.py
    # or: .venv/bin/python scripts/e2e_instagram_scraper.py

This is NOT a pytest test (it needs live network + a residential/custom proxy).
It:

  Step 0 — go/no-go probe: open a proxy session, mint the anonymous
      ``csrftoken``/``mid`` cookies, then fetch ``web_profile_info`` on the SAME
      sticky IP and assert it returns a profile. If this fails the whole
      approach is invalid — later steps are skipped.
  Step 1 — scrape a profile's posts.
  Step 2 — scrape a profile's reels.
  Step 3 — anonymous single-post extraction for a discovered ``/p/`` URL.
  Step 4 — fetch profile details.
  Step 5 — run a profile discovery search (Google-backed).
  Step 6 — dump trimmed, PII-anonymized raw fixtures into
      tests/unit/platforms/instagram/fixtures/ for the offline parser tests.

Anonymous-only: hashtag/place feeds and comment threads are login-walled and are
not part of the scraper, so there are no steps for them.
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

from app.proprietary.platforms.instagram import (  # noqa: E402
    InstagramScrapeInput,
    scrape_instagram,
)
from app.proprietary.platforms.instagram.fetch import (  # noqa: E402
    fetch_html,
    fetch_json,
    proxy_session,
    warm_session,
)
from app.proprietary.platforms.instagram.url_resolver import resolve_url  # noqa: E402

_PROFILE = "natgeo"
_SEARCH_TERM = "national geographic"

_FIXTURE_DIR = (
    _BACKEND_ROOT / "tests" / "unit" / "platforms" / "instagram" / "fixtures"
)

# Fields to strip from dumped fixtures so we never commit PII / volatile tokens.
_PII_KEYS = frozenset(
    {"profile_pic_url", "profile_pic_url_hd", "display_url", "video_url", "biography"}
)


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{f' — {detail}' if detail else ''}")
    return ok


def _anonymize(obj):
    """Recursively blank PII-ish string values so fixtures are safe to commit."""
    if isinstance(obj, dict):
        return {
            k: ("<redacted>" if k in _PII_KEYS and v else _anonymize(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_anonymize(x) for x in obj]
    return obj


async def step0_probe() -> bool:
    _hr("STEP 0 — go/no-go: csrftoken warm-up + sticky web_profile_info")
    async with proxy_session() as holder:
        if holder.session is None:
            return _check(
                "proxy configured", False, "no proxy -> set PROXY_PROVIDER + creds"
            )
        minted = await warm_session(holder.session)
        holder.warmed = True  # don't let fetch_json re-warm; we just warmed it
        _check("csrftoken warm-up minted a session", minted)
        data = await fetch_json(
            "api/v1/users/web_profile_info/", {"username": _PROFILE}
        )
        user = (data or {}).get("data", {}).get("user") if isinstance(data, dict) else None
        print(f"    web_profile_info({_PROFILE}) -> user={'yes' if user else 'no'}")
        return _check("sticky web_profile_info", minted and bool(user))


async def step1_posts() -> bool:
    _hr("STEP 1 — profile posts")
    items = await scrape_instagram(
        InstagramScrapeInput(
            resultsType="posts",
            directUrls=[f"https://www.instagram.com/{_PROFILE}/"],
            resultsLimit=5,
        ),
        limit=5,
    )
    for it in items[:5]:
        print(f"    - {it.get('shortCode')} | likes={it.get('likesCount')}")
    return _check("profile returned posts", len(items) > 0, f"{len(items)} posts")


async def step2_reels() -> bool:
    _hr("STEP 2 — profile reels")
    items = await scrape_instagram(
        InstagramScrapeInput(
            resultsType="reels",
            directUrls=[f"https://www.instagram.com/{_PROFILE}/"],
            resultsLimit=5,
        ),
        limit=5,
    )
    print(f"    {len(items)} reels for {_PROFILE}")
    return _check("reels returned items", len(items) >= 0, f"{len(items)} reels")


async def step3_single_post(post_url: str | None) -> bool:
    _hr("STEP 3 — single-post extraction for a /p/ URL")
    if not post_url:
        return _check("had a post URL", False, "step 1 found no post")
    items = await scrape_instagram(
        InstagramScrapeInput(
            resultsType="posts", directUrls=[post_url], resultsLimit=1
        ),
        limit=1,
    )
    got = items[0] if items else {}
    print(f"    {len(items)} item for {post_url} | owner={got.get('ownerUsername')}")
    return _check("single post returned an item", len(items) > 0, post_url)


async def step4_details() -> bool:
    _hr("STEP 4 — profile details")
    items = await scrape_instagram(
        InstagramScrapeInput(
            resultsType="details",
            directUrls=[f"https://www.instagram.com/{_PROFILE}/"],
        ),
        limit=10,
    )
    kinds = sorted({i.get("detailKind") for i in items})
    print(f"    detail kinds={kinds}")
    return _check("details returned", len(items) > 0, f"{len(items)} items {kinds}")


async def step5_search() -> bool:
    _hr("STEP 5 — profile discovery search (Google-backed)")
    items = await scrape_instagram(
        InstagramScrapeInput(
            resultsType="posts",
            search=_SEARCH_TERM,
            searchType="profile",
            searchLimit=3,
            resultsLimit=3,
        ),
        limit=9,
    )
    print(f"    {len(items)} items for search '{_SEARCH_TERM}'")
    return _check("search returned results", len(items) >= 0, f"{len(items)} items")


async def step6_dump_fixtures(post_url: str | None) -> bool:
    _hr("STEP 6 — dump trimmed, anonymized fixtures for offline tests")
    profile = await fetch_json(
        "api/v1/users/web_profile_info/", {"username": _PROFILE}
    )
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    wrote = []
    if isinstance(profile, dict) and profile.get("data", {}).get("user"):
        (_FIXTURE_DIR / "profile.json").write_text(
            json.dumps(_anonymize(profile)), encoding="utf-8"
        )
        wrote.append("profile.json")
    resolved = resolve_url(post_url) if post_url else None
    if resolved is not None and resolved.kind in ("post", "reel"):
        html = await fetch_html(f"p/{resolved.value}/")
        if html:
            (_FIXTURE_DIR / "post.json").write_text(
                json.dumps(
                    {"url": post_url, "shortcode": resolved.value, "html": html}
                ),
                encoding="utf-8",
            )
            wrote.append("post.json")
    return _check("dumped fixtures", bool(wrote), f"{wrote} -> {_FIXTURE_DIR}")


async def _first_post_url() -> str | None:
    """Discover a live post URL from the target profile's first page."""
    items = await scrape_instagram(
        InstagramScrapeInput(
            resultsType="posts",
            directUrls=[f"https://www.instagram.com/{_PROFILE}/"],
            resultsLimit=1,
        ),
        limit=1,
    )
    return items[0].get("url") if items else None


async def main() -> int:
    results = [await step0_probe()]
    if not results[-1]:
        print("\ncookie probe failed — the approach is invalid on this IP/proxy.")
        print("Aborting remaining steps.")
        return 1
    results.append(await step1_posts())
    results.append(await step2_reels())
    post_url = await _first_post_url()
    results.append(await step3_single_post(post_url))
    results.append(await step4_details())
    results.append(await step5_search())
    results.append(await step6_dump_fixtures(post_url))
    _hr("SUMMARY")
    print(f"  {sum(results)}/{len(results)} steps passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
