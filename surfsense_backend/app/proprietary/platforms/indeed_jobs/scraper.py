"""Orchestrator for the Indeed scraper.

:func:`iter_indeed` streams flat job items from one warmed browser session:
``startUrls`` (search/company pages) or ``queries`` are paged by the ``start``
offset, deduped by ``jobKey``, and stopped on the first page that adds nothing.
:func:`scrape_indeed` collects the stream under a caller ``limit``.

Targets run sequentially on a single session — a browser per target would cost
far more than the sequential paging it would save.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .fetch import IndeedSession, now_iso, open_session
from .parsers import extract_jobcards_blob, job_results, parse_job
from .schemas import IndeedItem, IndeedScrapeInput
from .url_resolver import build_search_url, resolve_url

logger = logging.getLogger(__name__)

__all__ = ["iter_indeed", "scrape_indeed"]

# Indeed's search pagination increments the ``start`` offset by 10.
_PAGE_STEP = 10
# Indeed stops serving useful results past ~1000; cap pages well before that.
_MAX_PAGES = 10


def _emit(partial: dict[str, Any]) -> dict[str, Any]:
    """Stamp ``scrapedAt`` and normalize through the output model."""
    return IndeedItem(**{**partial, "scrapedAt": now_iso()}).to_output()


def _with_start(url: str, start: int) -> str:
    """Return ``url`` with its ``start`` query param set (removed when 0)."""
    parsed = urlparse(url)
    params = [(k, v) for k, v in parse_qsl(parsed.query) if k != "start"]
    if start:
        params.append(("start", str(start)))
    return urlunparse(parsed._replace(query=urlencode(params)))


async def _paginate(
    session: IndeedSession, first_url: str, *, domain: str, max_items: int
) -> AsyncIterator[dict[str, Any]]:
    """Yield items across pages of one search/company URL, deduped by ``jobKey``."""
    if max_items <= 0:
        return
    base_url = f"https://{domain}"
    seen: set[str] = set()
    emitted = 0
    for page in range(_MAX_PAGES):
        html = await session.fetch_html(_with_start(first_url, page * _PAGE_STEP))
        raws = job_results(extract_jobcards_blob(html))
        if not raws:
            return
        added = 0
        for raw in raws:
            item = parse_job(raw, base_url=base_url)
            job_key = item.get("jobKey")
            if isinstance(job_key, str):
                if job_key in seen:
                    continue
                seen.add(job_key)
            yield _emit(item)
            emitted += 1
            added += 1
            if emitted >= max_items:
                return
        if added == 0:  # a whole page of duplicates: end of useful results
            return


def _targets(input_model: IndeedScrapeInput) -> list[tuple[str, str]]:
    """Resolve inputs to ``(url, domain)`` search/company targets.

    ``startUrls`` take precedence over ``queries``. Job (``/viewjob``) URLs are
    skipped here; detail enrichment is a separate flow.
    """
    if input_model.startUrls:
        out: list[tuple[str, str]] = []
        for entry in input_model.startUrls:
            resolved = resolve_url(entry.url)
            if resolved is None or resolved.kind == "job":
                logger.warning("[indeed] skipping unsupported URL: %s", entry.url)
                continue
            out.append((resolved.url, resolved.domain))
        return out

    domain = None
    urls: list[tuple[str, str]] = []
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
        urls.append((url, domain))
    return urls


async def iter_indeed(
    input_model: IndeedScrapeInput, session: IndeedSession
) -> AsyncIterator[dict[str, Any]]:
    """Stream flat job items for every target, deduped by ``jobKey`` across all."""
    global_seen: set[str] = set()
    for url, domain in _targets(input_model):
        async for item in _paginate(
            session, url, domain=domain, max_items=input_model.maxItemsPerQuery
        ):
            job_key = item.get("jobKey")
            if isinstance(job_key, str):
                if job_key in global_seen:
                    continue
                global_seen.add(job_key)
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
