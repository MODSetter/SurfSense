"""Manual functional e2e for the Reddit scraper (app/proprietary/platforms/reddit).

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/e2e_reddit_scraper.py
    # or: .venv/bin/python scripts/e2e_reddit_scraper.py

This is NOT a pytest test (it needs live network + a residential/custom proxy).
It:

  Step 0 — go/no-go probe (folds in the old scripts/reddit_probe.py): open a
      proxy session, warm a ``loid`` (svc/shreddit first, old.reddit fallback),
      then do sequential ``.json`` fetches on the SAME sticky IP and assert each
      returns a Reddit Listing. If this fails the whole approach is invalid —
      later steps are skipped.
  Step 1 — scrape a discovered post URL (post + a few comments).
  Step 2 — scrape a subreddit listing.
  Step 3 — run a search query.
  Step 4 — scrape a user profile.
  Step 5 — dump trimmed raw ``.json`` fixtures into
      tests/unit/platforms/reddit/fixtures/ for the offline parser tests.
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

from app.proprietary.platforms.reddit import (  # noqa: E402
    RedditScrapeInput,
    scrape_reddit,
)
from app.proprietary.platforms.reddit.fetch import (  # noqa: E402
    fetch_json,
    proxy_session,
    warm_session,
)
from app.proprietary.platforms.reddit.parsers import children  # noqa: E402

_SUBREDDIT = "python"
_SEARCH_TERM = "async web scraping"
_USER = "spez"

_FIXTURE_DIR = _BACKEND_ROOT / "tests" / "unit" / "platforms" / "reddit" / "fixtures"


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{f' — {detail}' if detail else ''}")
    return ok


def _listing_count(data) -> int | None:
    """Child count if ``data`` looks like a Reddit Listing (or post+comments)."""
    try:
        if isinstance(data, dict) and data.get("kind") == "Listing":
            return len(data["data"]["children"])
        if isinstance(data, list):
            return sum(
                len(x["data"]["children"])
                for x in data
                if isinstance(x, dict) and x.get("kind") == "Listing"
            )
    except Exception:
        return None
    return None


async def _first_post_permalink() -> str | None:
    """Discover a live post URL from the subreddit's hot listing."""
    listing = await fetch_json(f"r/{_SUBREDDIT}/hot", {"limit": 5})
    kids = children(listing)
    if not kids:
        return None
    permalink = (kids[0].get("data") or {}).get("permalink")
    return f"https://www.reddit.com{permalink}" if permalink else None


async def step0_probe() -> bool:
    _hr("STEP 0 — go/no-go: loid warm-up + sticky .json")
    async with proxy_session() as holder:
        if holder.session is None:
            return _check(
                "proxy configured", False, "no proxy -> set PROXY_PROVIDER + creds"
            )
        minted = await warm_session(holder.session)
        holder.warmed = True  # don't let fetch_json re-warm; we just warmed it
        _check("loid warm-up minted a session", minted)
        oks: list[bool] = []
        for path in (f"r/{_SUBREDDIT}/hot", "r/programming/new", f"r/{_SUBREDDIT}/hot"):
            data = await fetch_json(path, {"limit": 5})
            n = _listing_count(data)
            print(f"    {path} -> listing_count={n}")
            oks.append(n is not None and n > 0)
            await asyncio.sleep(1.0)
        return _check("sequential .json on sticky IP", minted and all(oks))


async def step1_post() -> bool:
    _hr("STEP 1 — scrape a discovered post (post + comments)")
    url = await _first_post_permalink()
    if not url:
        return _check("discovered a post URL", False)
    items = await scrape_reddit(
        RedditScrapeInput(startUrls=[{"url": url}], maxComments=5)
    )
    posts = [i for i in items if i.get("dataType") == "post"]
    comments = [i for i in items if i.get("dataType") == "comment"]
    print(f"    posts={len(posts)} comments={len(comments)} url={url}")
    return _check("post scraped", bool(posts) and bool(posts[0].get("id")))


async def step2_subreddit() -> bool:
    _hr("STEP 2 — scrape a subreddit listing")
    items = await scrape_reddit(
        RedditScrapeInput(
            startUrls=[{"url": f"https://www.reddit.com/r/{_SUBREDDIT}/hot"}],
            maxPostCount=5,
            skipComments=True,
        )
    )
    posts = [i for i in items if i.get("dataType") == "post"]
    for it in posts[:5]:
        print(f"    - {it.get('id')} | {it.get('title')}")
    return _check("subreddit returned posts", len(posts) > 0, f"{len(posts)} posts")


async def step3_search() -> bool:
    _hr("STEP 3 — search query")
    items = await scrape_reddit(
        RedditScrapeInput(searches=[_SEARCH_TERM], sort="relevance", maxItems=5)
    )
    for it in items[:5]:
        print(f"    - {it.get('id')} | {it.get('title')}")
    return _check("search returned results", len(items) > 0, f"{len(items)} items")


async def step4_user() -> bool:
    _hr("STEP 4 — user profile")
    items = await scrape_reddit(
        RedditScrapeInput(
            startUrls=[{"url": f"https://www.reddit.com/user/{_USER}"}], maxItems=5
        )
    )
    print(f"    {len(items)} items for u/{_USER}")
    return _check("user returned items", len(items) > 0, f"{len(items)} items")


async def step5_dump_fixtures() -> bool:
    _hr("STEP 5 — dump trimmed .json fixtures for offline tests")
    listing = await fetch_json(f"r/{_SUBREDDIT}/hot", {"limit": 25})
    url = await _first_post_permalink()
    post = None
    if url:
        path = url.split("reddit.com/")[-1].strip("/")
        post = await fetch_json(path, {"limit": 20})

    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    wrote = []
    if _listing_count(listing):
        (_FIXTURE_DIR / "sample_listing.json").write_text(
            json.dumps(listing), encoding="utf-8"
        )
        wrote.append("sample_listing.json")
    if isinstance(post, list) and post:
        (_FIXTURE_DIR / "sample_post.json").write_text(
            json.dumps(post), encoding="utf-8"
        )
        wrote.append("sample_post.json")
        # A single comment thing, for the comment-mapping fixture.
        comment_kids = children(post[1]) if len(post) > 1 else []
        first_comment = next((c for c in comment_kids if c.get("kind") == "t1"), None)
        if first_comment:
            (_FIXTURE_DIR / "sample_comment.json").write_text(
                json.dumps(first_comment), encoding="utf-8"
            )
            wrote.append("sample_comment.json")
    return _check("dumped fixtures", bool(wrote), f"{wrote} -> {_FIXTURE_DIR}")


async def main() -> int:
    results = [await step0_probe()]
    if not results[-1]:
        print("\nloid probe failed — the approach is invalid on this IP/proxy.")
        print("Aborting remaining steps.")
        return 1
    results.append(await step1_post())
    results.append(await step2_subreddit())
    results.append(await step3_search())
    results.append(await step4_user())
    results.append(await step5_dump_fixtures())
    _hr("SUMMARY")
    print(f"  {sum(results)}/{len(results)} steps passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
