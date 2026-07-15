"""Manual functional e2e for the Indeed scraper (app/proprietary/platforms/indeed_jobs).

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/e2e_indeed_scraper.py
    # or: .venv/bin/python scripts/e2e_indeed_scraper.py

This is NOT a pytest test (it needs live network + a residential/custom proxy).
All steps share one warmed browser session:

  Step 0 — go/no-go probe: open a session, fetch a live search page, and assert
      its embedded job-cards blob parses into results. If this fails the whole
      approach is blocked on this IP/proxy — later steps are skipped.
  Step 1 — search query -> job items; keep one discovered /viewjob URL.
  Step 2 — scrape a search URL via startUrls.
  Step 3 — scrape the discovered /viewjob URL and assert a full description.
  Step 4 — scrape_job_details enrichment: a query with detail pages fetched.
"""

import asyncio
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

from app.proprietary.platforms.indeed_jobs import (  # noqa: E402
    IndeedScrapeInput,
    scrape_indeed,
)
from app.proprietary.platforms.indeed_jobs.fetch import open_session  # noqa: E402
from app.proprietary.platforms.indeed_jobs.parsers import (  # noqa: E402
    extract_jobcards_blob,
    job_results,
)
from app.proprietary.platforms.indeed_jobs.url_resolver import (  # noqa: E402
    build_search_url,
)

_QUERY = "data analyst"
_LOCATION = "Remote"


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{f' — {detail}' if detail else ''}")
    return ok


async def step0_probe(sess, state: dict) -> bool:
    _hr("STEP 0 — go/no-go: warmed session + parseable job cards")
    url = build_search_url(_QUERY, location=_LOCATION)
    html = await sess.fetch_html(url)
    raws = job_results(extract_jobcards_blob(html))
    print(f"    {url} -> job_cards={len(raws)}")
    return _check("search page parsed job cards", len(raws) > 0, f"{len(raws)} cards")


async def step1_search(sess, state: dict) -> bool:
    _hr("STEP 1 — search query -> items")
    items = await scrape_indeed(
        IndeedScrapeInput(queries=[_QUERY], location=_LOCATION, maxItems=5),
        limit=5,
        session=sess,
    )
    for it in items[:5]:
        print(f"    - {it.get('jobKey')} | {it.get('title')} @ {it.get('company')}")
    state["job_url"] = next(
        (it["jobUrl"] for it in items if it.get("jobUrl")), None
    )
    return _check("search returned jobs", len(items) > 0, f"{len(items)} jobs")


async def step2_search_url(sess, state: dict) -> bool:
    _hr("STEP 2 — scrape a search URL (startUrls)")
    url = build_search_url(_QUERY, location=_LOCATION)
    items = await scrape_indeed(
        IndeedScrapeInput(startUrls=[{"url": url}], maxItems=5),
        limit=5,
        session=sess,
    )
    return _check("search URL returned jobs", len(items) > 0, f"{len(items)} jobs")


async def step3_viewjob(sess, state: dict) -> bool:
    _hr("STEP 3 — scrape a discovered /viewjob URL (full description)")
    url = state.get("job_url")
    if not url:
        return _check("had a discovered job URL", False)
    items = await scrape_indeed(
        IndeedScrapeInput(startUrls=[{"url": url}], maxItems=1),
        limit=1,
        session=sess,
    )
    desc = items[0].get("descriptionText") if items else None
    print(f"    url={url}\n    description_chars={len(desc or '')}")
    return _check("viewjob returned a description", bool(desc), url)


async def step4_enrich(sess, state: dict) -> bool:
    _hr("STEP 4 — search with scrape_job_details enrichment")
    items = await scrape_indeed(
        IndeedScrapeInput(
            queries=[_QUERY],
            location=_LOCATION,
            maxItems=3,
            scrapeJobDetails=True,
        ),
        limit=3,
        session=sess,
    )
    # descriptionHtml is set only by the detail page; listings never carry it,
    # so it proves enrichment actually merged the /viewjob model.
    enriched = [i for i in items if i.get("descriptionHtml")]
    return _check(
        "enriched items carry full descriptionHtml",
        bool(enriched),
        f"{len(enriched)}/{len(items)} enriched",
    )


async def main() -> int:
    state: dict = {}
    async with open_session() as sess:
        results = [await step0_probe(sess, state)]
        if not results[-1]:
            print("\nprobe failed — Indeed is blocking this IP/proxy. Aborting.")
            return 1
        results.append(await step1_search(sess, state))
        results.append(await step2_search_url(sess, state))
        results.append(await step3_viewjob(sess, state))
        results.append(await step4_enrich(sess, state))
    _hr("SUMMARY")
    print(f"  {sum(results)}/{len(results)} steps passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
