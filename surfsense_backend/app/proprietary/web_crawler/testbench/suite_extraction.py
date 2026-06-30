# SurfSense proprietary crawler engine.
#
# This module is part of the ``app.proprietary`` package and is licensed
# SEPARATELY from the Apache-2.0 project root. See ``app/proprietary/LICENSE``.
# Do not relicense or redistribute this file under Apache-2.0.
"""Suite E — extraction correctness (separate axis from stealth).

Unlike Suite S, this drives the **real ``crawl_url`` ladder end-to-end** — the
auto-tier + Trafilatura markdown path is exactly the production behavior we want
to assert. Targets are purpose-built, ToS-safe scraping sandboxes with known
content, so extraction regressions are caught deterministically (a missing
expected string => FAIL). The ``/js`` cases exercise the DynamicFetcher (browser)
tier; the static catalogs exercise the HTTP tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.proprietary.web_crawler import CrawlOutcomeStatus, WebCrawlerConnector

from .core import CheckResult, CheckStatus


@dataclass
class ExtractionCase:
    """A sandbox URL + strings that must appear in the extracted markdown."""

    name: str
    url: str
    must_contain: list[str] = field(default_factory=list)


_CASES: list[ExtractionCase] = [
    ExtractionCase(
        name="books_static",
        url="https://books.toscrape.com/",
        must_contain=["A Light in the Attic", "Tipping the Velvet"],
    ),
    ExtractionCase(
        name="quotes_static",
        url="https://quotes.toscrape.com/",
        must_contain=["Albert Einstein", "world as we have created it"],
    ),
    ExtractionCase(
        name="quotes_js_rendered",
        url="https://quotes.toscrape.com/js/",
        must_contain=["Albert Einstein", "world as we have created it"],
    ),
    ExtractionCase(
        name="scrapethissite_simple",
        url="https://www.scrapethissite.com/pages/simple/",
        must_contain=["Andorra", "Afghanistan"],
    ),
]


def _content_of(outcome) -> str:
    result = getattr(outcome, "result", None) or {}
    if isinstance(result, dict):
        return str(result.get("content") or "")
    return ""


async def _run_case(
    connector: WebCrawlerConnector, case: ExtractionCase
) -> CheckResult:
    bar = f"SUCCESS + contains {len(case.must_contain)} marker(s)"
    try:
        outcome = await connector.crawl_url(case.url)
    except Exception as exc:  # noqa: BLE001 - never crash the run
        return CheckResult(
            suite="E",
            name=case.name,
            tier="crawl_url",
            status=CheckStatus.ERROR,
            bar=bar,
            detail=f"{type(exc).__name__}: {exc}",
        )

    tier = getattr(outcome, "tier", None) or "crawl_url"
    if outcome.status is not CrawlOutcomeStatus.SUCCESS:
        return CheckResult(
            suite="E",
            name=case.name,
            tier=tier,
            status=CheckStatus.FAIL,
            bar=bar,
            detail=f"status={outcome.status.value}: {outcome.error or ''}"[:160],
        )

    content = _content_of(outcome)
    lowered = content.lower()
    missing = [m for m in case.must_contain if m.lower() not in lowered]
    if missing:
        return CheckResult(
            suite="E",
            name=case.name,
            tier=tier,
            status=CheckStatus.FAIL,
            bar=bar,
            detail=f"missing {missing} (len={len(content)})",
            numeric=float(len(content)),
        )
    return CheckResult(
        suite="E",
        name=case.name,
        tier=tier,
        status=CheckStatus.PASS,
        bar=bar,
        detail=f"all markers present (tier={tier}, len={len(content)})",
        numeric=float(len(content)),
    )


async def run_suite_e() -> list[CheckResult]:
    """Run the extraction-correctness cases against the live sandboxes."""
    connector = WebCrawlerConnector()
    results: list[CheckResult] = []
    for case in _CASES:
        print(f"  [E] {case.name} -> {case.url}")
        results.append(await _run_case(connector, case))
    return results
