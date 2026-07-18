"""Live end-to-end checks for the Google Search scraper (needs proxy + browser).

    .venv/Scripts/python.exe scripts/e2e_google_search.py

Covers: a plain query, a site: filter, text ads, product ads, the
focusOnPaidAds retry (commercial = ads found; non-commercial = retries capped,
organic still returned), People-Also-Ask answer expansion, sitelinks, the AI
Overview, the mobile layout, filter=0, base64 icons, and Google AI Mode.

Pass case names as args to run a subset, e.g.:

    .venv/Scripts/python.exe scripts/e2e_google_search.py paa
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
load_dotenv(_ROOT / ".env")

logging.basicConfig(level=logging.WARNING)
for _name in (
    "app.proprietary.platforms.google_search.scraper",
    "app.proprietary.platforms.google_search.fetch",
    "app.proprietary.platforms.google_search.captcha",
):
    logging.getLogger(_name).setLevel(logging.INFO)

from app.proprietary.platforms.google_search import (  # noqa: E402
    GoogleSearchScrapeInput,
    scrape_serps,
)
from app.proprietary.platforms.google_search.fetch import close_sessions  # noqa: E402


async def run_ai_mode(label: str, *, queries: str) -> None:
    print(f"\n=== {label} ===")
    t0 = time.perf_counter()
    inp = GoogleSearchScrapeInput(
        queries=queries,
        countryCode="us",
        languageCode="en",
        aiModeSearch={"enableAiMode": True},
    )
    items = await scrape_serps(inp, limit=2)
    ai_items = [i for i in items if i["aiModeResult"]]
    assert ai_items, f"{label}: no aiModeResult item emitted"
    res = ai_items[0]["aiModeResult"]
    print(
        f"  text={len(res['text'])} chars, sources={len(res['sources'])} "
        f"({time.perf_counter() - t0:.0f}s)"
    )
    print(f"  {res['text'][:130]!r}")
    for s in res["sources"][:3]:
        print(f"    src: {(s['title'] or '')[:60]!r}")
    assert res["text"] and len(res["text"]) > 100, f"{label}: answer too short"
    assert res["sources"], f"{label}: no cited sources"
    assert "udm=50" in ai_items[0]["searchQuery"]["url"]


async def run(
    label: str,
    *,
    expect_ads=False,
    expect_products=False,
    expect_paa_answers=False,
    expect_sitelinks=False,
    expect_aio=False,
    expect_device=None,
    expect_icons=False,
    **kwargs,
) -> None:
    print(f"\n=== {label} ===")
    t0 = time.perf_counter()
    inp = GoogleSearchScrapeInput(countryCode="us", languageCode="en", **kwargs)
    items = await scrape_serps(inp, limit=1)
    assert items, f"{label}: no SERP item"
    it = items[0]
    paa_answered = [p for p in it["peopleAlsoAsk"] if p["answer"]]
    sitelinked = [o for o in it["organicResults"] if o["siteLinks"]]
    print(f"  term={it['searchQuery']['term']!r} resultsTotal={it['resultsTotal']}")
    print(
        f"  organic={len(it['organicResults'])} paidResults={len(it['paidResults'])} "
        f"paidProducts={len(it['paidProducts'])} related={len(it['relatedQueries'])} "
        f"suggested={len(it['suggestedResults'])} "
        f"paa={len(it['peopleAlsoAsk'])} (answered={len(paa_answered)}) "
        f"({time.perf_counter() - t0:.0f}s)"
    )
    for o in sitelinked[:2]:
        print(
            f"    [sitelinks on #{o['position']}] "
            + ", ".join(s["title"] for s in o["siteLinks"][:5])
        )
    aio = it["aiOverview"]
    if aio:
        print(
            f"    [aiOverview] content={len(aio['content'])} chars, "
            f"sources={len(aio['sources'])}"
        )
        print(f"        {aio['content'][:110]!r}")
        for s in aio["sources"][:3]:
            print(f"        src: {(s['title'] or '')[:55]!r}")
    for a in it["paidResults"][:3]:
        print(f"    [ad {a['adPosition']}] {a['title'][:44]!r} {(a['url'] or '')[:45]}")
    for p in it["paidProducts"][:3]:
        print(f"    [pla] {p['title'][:40]!r} {p['prices']} {p['displayedUrl']}")
    for p in paa_answered[:3]:
        print(f"    [paa] {p['question'][:48]!r}")
        print(f"          A: {p['answer'][:90]!r}")
        print(f"          src: {p['url'] or '-'} | {(p['title'] or '-')[:45]}")
    assert it["organicResults"], f"{label}: no organic results"
    if expect_ads:
        assert it["paidResults"], f"{label}: expected text ads, got none"
    if expect_products:
        assert it["paidProducts"], f"{label}: expected product ads, got none"
    if expect_paa_answers:
        assert paa_answered, f"{label}: expected PAA answers, got none"
    if expect_sitelinks:
        assert sitelinked, f"{label}: expected sitelinks, got none"
        assert it["suggestedResults"], f"{label}: expected suggestedResults"
    if expect_aio:
        assert aio and aio["content"], f"{label}: expected an AI Overview"
        assert aio["sources"], f"{label}: expected AI Overview sources"
    if expect_device:
        assert it["searchQuery"]["device"] == expect_device, (
            f"{label}: device={it['searchQuery']['device']}"
        )
    if expect_icons:
        iconed = [
            o
            for o in it["organicResults"]
            if (o["icon"] or "").startswith("data:image")
        ]
        print(
            f"    [icons] {len(iconed)}/{len(it['organicResults'])} organic "
            f"carry a base64 favicon"
        )
        assert iconed, f"{label}: expected base64 icons on organic results"


_CASES = {
    "plain": lambda: run("plain query", queries="python asyncio tutorial"),
    # Prod incident 2026-07-17: single-word brand/navigational queries were
    # exhausting all 24 IPs (precheck 200 but the browser render 429-walled).
    "brand": lambda: run("brand query (notebooklm, prod repro)", queries="notebooklm"),
    "site": lambda: run("site: filter", queries="machine learning", site="arxiv.org"),
    "ads": lambda: run("text ads", queries="car insurance quotes", expect_ads=True),
    "products": lambda: run(
        "product ads", queries="buy running shoes", expect_products=True
    ),
    "focus": lambda: run(
        "focusOnPaidAds (commercial)",
        queries="car insurance quotes",
        focusOnPaidAds=True,
        expect_ads=True,
    ),
    "focus-neg": lambda: run(
        "focusOnPaidAds (non-commercial, retries capped)",
        queries="python asyncio tutorial",
        focusOnPaidAds=True,
    ),
    "paa": lambda: run(
        "people also ask", queries="what is seo", expect_paa_answers=True
    ),
    "sitelinks": lambda: run(
        "sitelinks + suggested (brand query)", queries="amazon", expect_sitelinks=True
    ),
    "aio": lambda: run("AI Overview", queries="benefits of green tea", expect_aio=True),
    "mobile": lambda: run(
        "mobile layout (mobileResults)",
        queries="best seo tools",
        mobileResults=True,
        expect_device="MOBILE",
    ),
    "unfiltered": lambda: run(
        "includeUnfilteredResults (filter=0)",
        queries="python asyncio tutorial",
        includeUnfilteredResults=True,
    ),
    "icons": lambda: run(
        "includeIcons (base64 favicons)",
        queries="github",
        includeIcons=True,
        expect_icons=True,
    ),
    "aimode": lambda: run_ai_mode(
        "Google AI Mode (udm=50)", queries="what is quantum computing"
    ),
}


async def main() -> None:
    names = sys.argv[1:] or list(_CASES)
    try:
        for name in names:
            await _CASES[name]()
    finally:
        await close_sessions()
    print("\nALL E2E OK")


if __name__ == "__main__":
    asyncio.run(main())
