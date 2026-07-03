"""Manual functional e2e for Phase 3 crawler + billing (3a / 3b / 3c).

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/e2e_phase3_crawl_billing.py
    # or: .\\.venv\\Scripts\\python.exe scripts/e2e_phase3_crawl_billing.py

What it exercises (everything REAL — live network, live proxy, live DB reads):

  Stage 1 (3a + 3b) — direct fetch + proxy egress-IP proof + crawl_url ladder.
  Stage 2 (3c chat surface) — the scrape_webpage tool folds one successful
      crawl into the current chat turn's accumulator (billed at finalize).

This is NOT a pytest test (it needs a live stack + proxy creds + network). It
is the manual functional counterpart to the unit suites; the undetectability /
anti-bot scorecard is a separate deliverable (03f), after 03d/03e.
"""

import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

# --- bootstrap: load .env and put the backend root on sys.path before app.* ---
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))
for _candidate in (_BACKEND_ROOT / ".env", _BACKEND_ROOT.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break


from app.config import config  # noqa: E402

# Content-rich, generally crawl-friendly targets (real extraction expected).
_ARTICLE_URLS = [
    "https://en.wikipedia.org/wiki/Competitive_intelligence",
    "https://en.wikipedia.org/wiki/Market_research",
]
_IP_ECHO = "https://api.ipify.org?format=json"


def _mask(url: str | None) -> str:
    if not url:
        return "<none>"
    p = urlsplit(url)
    host = p.hostname or "?"
    port = f":{p.port}" if p.port else ""
    creds = "***@" if p.username else ""
    return f"{p.scheme}://{creds}{host}{port}"


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{f' — {detail}' if detail else ''}")
    return ok


# ===========================================================================
# Stage 1 — crawl core (3a) + proxy routing (3b)
# ===========================================================================
async def stage1_crawl_and_proxy() -> bool:
    _hr("STAGE 1 — crawl_url ladder (3a) + proxy egress (3b)")
    from scrapling.fetchers import AsyncFetcher

    from app.proprietary.web_crawler import CrawlOutcomeStatus, WebCrawlerConnector
    from app.utils.proxy import get_active_provider, get_proxy_url, is_pool_backed

    ok = True
    provider = get_active_provider()
    proxy_url = get_proxy_url()
    print(f"  active proxy provider : {provider.name}")
    print(f"  proxy url             : {_mask(proxy_url)}")
    print(f"  pool-backed (rotates) : {is_pool_backed()}")

    # Proxy egress-IP proof: direct IP vs proxied IP should differ.
    direct_ip = proxied_ip = None
    try:
        direct = await AsyncFetcher.get(_IP_ECHO, impersonate="chrome", timeout=30)
        direct_ip = direct.json().get("ip")
    except Exception as exc:
        print(f"  [INFO] direct IP fetch failed: {exc}")
    if proxy_url:
        try:
            via = await AsyncFetcher.get(
                _IP_ECHO, impersonate="chrome", proxy=proxy_url, timeout=45
            )
            proxied_ip = via.json().get("ip")
        except Exception as exc:
            print(f"  [INFO] proxied IP fetch failed: {exc}")
    print(f"  egress IP (direct)    : {direct_ip}")
    print(f"  egress IP (via proxy) : {proxied_ip}")
    if proxy_url:
        ok &= _check(
            "proxy changes egress IP",
            bool(proxied_ip) and proxied_ip != direct_ip,
            f"{direct_ip} -> {proxied_ip}",
        )
    else:
        print("  [INFO] no proxy configured — skipping egress-IP assertion")

    # crawl_url end-to-end on a content-rich page.
    crawler = WebCrawlerConnector()
    outcome = await crawler.crawl_url(_ARTICLE_URLS[0])
    content = (outcome.result or {}).get("content", "") if outcome.result else ""
    tier = (outcome.result or {}).get("crawler_type", "?") if outcome.result else "?"
    ok &= _check(
        "crawl_url returns SUCCESS with content",
        outcome.status is CrawlOutcomeStatus.SUCCESS and len(content) > 200,
        f"status={outcome.status.value} tier={tier} chars={len(content)}",
    )
    return ok


# ===========================================================================
# Stage 2 — chat scrape folds cost into the turn accumulator (3c surface 2)
# ===========================================================================
async def stage2_chat_fold() -> bool:
    _hr("STAGE 2 — chat scrape_webpage folds crawl cost into turn (3c)")
    config.WEB_CRAWL_CREDIT_BILLING_ENABLED = True
    price = config.WEB_CRAWL_MICROS_PER_SUCCESS

    from app.agents.chat.multi_agent_chat.main_agent.tools.scrape_webpage import (
        create_scrape_webpage_tool,
    )
    from app.services.token_tracking_service import start_turn

    acc = start_turn()
    tool = create_scrape_webpage_tool()
    result = await tool.ainvoke({"url": _ARTICLE_URLS[0]})
    crawled_ok = "error" not in result and bool(result.get("content"))
    print(f"  scrape error          : {result.get('error', '<none>')}")
    print(f"  turn cost_micros      : {acc.total_cost_micros}")
    print(f"  call kinds            : {[c.call_kind for c in acc.calls]}")
    if not crawled_ok:
        print("  [INFO] crawl did not succeed (site/proxy) — cannot assert fold")
        return False
    return _check(
        "one web_crawl line folded at configured price",
        acc.total_cost_micros == price
        and any(c.call_kind == "web_crawl" for c in acc.calls),
        f"expected={price} got={acc.total_cost_micros}",
    )


async def main() -> int:
    print("Phase 3 functional e2e (3a/3b/3c) — live network + proxy, DB rolled back")
    results: dict[str, bool] = {}
    for name, coro in (
        ("Stage 1 crawl+proxy", stage1_crawl_and_proxy),
        ("Stage 2 chat fold", stage2_chat_fold),
    ):
        try:
            results[name] = await coro()
        except Exception as exc:
            import traceback

            traceback.print_exc()
            print(f"  [ERROR] {name} raised: {exc}")
            results[name] = False

    _hr("SUMMARY")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL/SKIP'} — {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
