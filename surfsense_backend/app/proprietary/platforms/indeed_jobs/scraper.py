"""Orchestrator for the Indeed scraper.

:func:`iter_indeed` streams deduped job items from one warmed session; each
search/company target contributes its first page. :func:`scrape_indeed` collects
the stream under a caller ``limit``. Targets run sequentially to reuse the session.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

from .fetch import IndeedSession, now_iso, open_session
from .parsers import (
    extract_jobcards_blob,
    job_results,
    parse_job,
    parse_job_detail,
)
from .schemas import IndeedItem, IndeedScrapeInput
from .url_resolver import build_search_url, resolve_url

logger = logging.getLogger(__name__)

__all__ = ["iter_indeed", "scrape_indeed"]


def _emit(partial: dict[str, Any]) -> dict[str, Any]:
    """Stamp ``scrapedAt`` and normalize through the output model."""
    return IndeedItem(**{**partial, "scrapedAt": now_iso()}).to_output()


async def _search_items(
    session: IndeedSession, url: str, *, domain: str, max_items: int
) -> AsyncIterator[dict[str, Any]]:
    """Yield deduped job cards from one search/company page.

    ponytail: caps a query at its first page (~15 jobs) — anonymous Indeed gates
    ``start>=10``; deeper depth needs an authenticated session or Indeed's API.
    """
    if max_items <= 0:
        return
    base_url = f"https://{domain}"
    html = await session.fetch_html(url)
    seen: set[str] = set()
    emitted = 0
    for raw in job_results(extract_jobcards_blob(html)):
        item = parse_job(raw, base_url=base_url)
        job_key = item.get("jobKey")
        if isinstance(job_key, str):
            if job_key in seen:
                continue
            seen.add(job_key)
        yield _emit(item)
        emitted += 1
        if emitted >= max_items:
            return


def _targets(input_model: IndeedScrapeInput) -> list[tuple[str, str, str]]:
    """Resolve inputs to ``(kind, url, domain)`` targets.

    ``startUrls`` take precedence over ``queries``. ``kind`` is ``search`` for
    query-built and search/company URLs, or ``job`` for a ``/viewjob`` URL.
    """
    if input_model.startUrls:
        out: list[tuple[str, str, str]] = []
        for entry in input_model.startUrls:
            resolved = resolve_url(entry.url)
            if resolved is None:
                logger.warning("[indeed] skipping unrecognized URL: %s", entry.url)
                continue
            kind = "job" if resolved.kind == "job" else "search"
            out.append((kind, resolved.url, resolved.domain))
        return out

    domain = None
    urls: list[tuple[str, str, str]] = []
    for query in input_model.queries:
        url = build_search_url(
            query,
            country=input_model.country,
            location=input_model.location,
            radius=input_model.radius,
            job_type=input_model.jobType,
            level=input_model.level,
            remote=input_model.remote,
            from_days=input_model.fromDays,
            sort=input_model.sort,
        )
        domain = domain or urlparse(url).hostname or "www.indeed.com"
        urls.append(("search", url, domain))
    return urls


async def _enrich(session: IndeedSession, item: dict[str, Any], base_url: str) -> None:
    """Merge a job's /viewjob detail (full description, etc.) onto ``item`` in place.

    Best-effort: a blocked or malformed detail page leaves the listing fields as-is
    rather than failing the run.
    """
    job_url = item.get("jobUrl")
    if not isinstance(job_url, str):
        return
    try:
        # Fail fast: enrichment is best-effort, so a gated detail page must not
        # rotate IPs and eat the run's time budget for one job's description.
        html = await session.fetch_html(job_url, max_rotations=0)
        detail = parse_job_detail(html, base_url=base_url)
    except Exception as exc:
        logger.warning("[indeed] detail fetch failed for %s: %s", job_url, exc)
        return
    item.update(detail)


async def _job_item(
    session: IndeedSession, url: str, base_url: str
) -> dict[str, Any] | None:
    """Scrape a single /viewjob URL into an item from its detail page alone."""
    detail = parse_job_detail(await session.fetch_html(url), base_url=base_url)
    if not detail:
        return None
    return _emit({"jobUrl": url, "source": "indeed", **detail})


async def iter_indeed(
    input_model: IndeedScrapeInput, session: IndeedSession
) -> AsyncIterator[dict[str, Any]]:
    """Stream flat job items for every target, deduped by ``jobKey`` across all."""
    global_seen: set[str] = set()
    for kind, url, domain in _targets(input_model):
        base_url = f"https://{domain}"
        if kind == "job":
            item = await _job_item(session, url, base_url)
            if item is not None:
                yield item
            continue
        async for item in _search_items(
            session, url, domain=domain, max_items=input_model.maxItemsPerQuery
        ):
            job_key = item.get("jobKey")
            if isinstance(job_key, str):
                if job_key in global_seen:
                    continue
                global_seen.add(job_key)
            if input_model.scrapeJobDetails:
                await _enrich(session, item, base_url)
            yield item


async def scrape_indeed(
    input_model: IndeedScrapeInput,
    *,
    limit: int | None = None,
    session: IndeedSession | None = None,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_indeed` into a list under an optional ``limit``.

    Opens a warmed session when one is not supplied. ``limit`` is a request-time
    guard, not a ceiling baked into the stream.
    """
    from app.capabilities.core.progress import emit_progress

    async def _collect(sess: IndeedSession) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        async for item in iter_indeed(input_model, sess):
            results.append(item)
            emit_progress("scraping", current=len(results), total=limit, unit="item")
            if limit is not None and len(results) >= limit:
                break
        return results

    if session is not None:
        return await _collect(session)
    async with open_session() as sess:
        return await _collect(sess)
