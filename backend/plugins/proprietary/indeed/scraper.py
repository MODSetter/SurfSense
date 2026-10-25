"""Orchestrator for the Indeed scraper.

:func:`iter_indeed` streams deduped job items for every target; each search or
company target contributes its first page, with its job details fetched from that
page when asked. Targets run a few at once (each on its own page of the country's
kept browser context) and are merged in input order, so the dedupe and limits
behave as if they ran one after another. :func:`scrape_indeed` collects the stream
under a caller ``limit``.

Kill switch: ``INDEED_TARGET_CONCURRENCY=1`` runs targets one at a time.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from typing import Any
from urllib.parse import urlparse

from proprietary.scraping.concurrency import ordered_map
from proprietary.scraping.logged_host import logged_host

from .fetch import IndeedSession, now_iso, open_session
from .parsers import (
    extract_jobcards_blob,
    inline_viewjob,
    job_results,
    parse_job,
    parse_job_detail_model,
)
from .schemas import IndeedItem, IndeedScrapeInput
from .url_resolver import build_search_url, resolve_url

logger = logging.getLogger(__name__)

__all__ = ["iter_indeed", "scrape_indeed"]


def _concurrency() -> int:
    try:
        return max(1, int(os.getenv("INDEED_TARGET_CONCURRENCY", "") or 3))
    except ValueError:
        return 3


# Targets in flight at once; the pool lends at most 3 pages per kept context.
_CONCURRENCY = _concurrency()


def _emit(partial: dict[str, Any]) -> dict[str, Any]:
    """Stamp ``scrapedAt`` and normalize through the output model."""
    return IndeedItem(**{**partial, "scrapedAt": now_iso()}).to_output()


def _cards(html: str, max_items: int) -> list[dict[str, Any]]:
    """The page's first ``max_items`` job cards, deduped by job key.

    ponytail: caps a query at its first page (36-45 jobs today): anonymous Indeed
    gates ``start>=10``; deeper depth needs an authenticated session or its API.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for raw in job_results(extract_jobcards_blob(html)):
        if len(out) >= max_items:
            break
        job_key = raw.get("jobkey")
        if isinstance(job_key, str):
            if job_key in seen:
                continue
            seen.add(job_key)
        out.append(raw)
    return out


def _spa_url(raw: dict[str, Any]) -> str:
    """The page-relative ``spa=1`` URL for a card: Indeed's own pane link first."""
    link = raw.get("viewJobLink")
    if isinstance(link, str) and link.startswith("/viewjob?"):
        return f"{link}&spa=1"
    return f"/viewjob?jk={raw.get('jobkey')}&spa=1"


async def _search_items(
    session: IndeedSession,
    url: str,
    *,
    domain: str,
    max_items: int,
    company_slug: str | None = None,
    details: bool = False,
    seen: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """Job items from one search/company page, with their details when asked.

    ``company_slug`` marks a ``/cmp/<slug>/jobs`` page, whose cards carry no
    company link. ``seen`` holds keys earlier targets already gave, whose details
    are not worth fetching again.
    """
    if max_items <= 0:
        return []
    base_url = f"https://{domain}"

    def wanted(html: str) -> dict[str, str]:
        # Runs on the browser loop, between the page load and the detail fetches.
        inline = inline_viewjob(html)
        skip = {inline.get("jobKey")} if inline else set()
        return {
            raw["jobkey"]: _spa_url(raw)
            for raw in _cards(html, max_items)
            if isinstance(raw.get("jobkey"), str)
            and raw["jobkey"] not in seen
            and raw["jobkey"] not in skip
        }

    fetched = await session.fetch_page(url, details_for=wanted if details else None)
    models = fetched.details
    if details:
        # The page's inline answer for its first job saves one spa=1 request.
        inline = inline_viewjob(fetched.html)
        if inline and isinstance(inline.get("jobKey"), str):
            models = {inline["jobKey"]: inline, **models}
    items: list[dict[str, Any]] = []
    for raw in _cards(fetched.html, max_items):
        item = parse_job(raw, base_url=base_url)
        if company_slug and not item.get("companyUrl"):
            item["companyUrl"] = f"{base_url}/cmp/{company_slug}"
        job_key = item.get("jobKey")
        if details and job_key not in seen:
            model = models.get(job_key)
            if model is None:
                logger.warning("[indeed] a job's detail fetch failed")
            else:
                _merge_detail(item, parse_job_detail_model(model, base_url=base_url))
        items.append(_emit(item))
    return items


def _targets(input_model: IndeedScrapeInput) -> list[tuple[str, str, str, str]]:
    """Resolve inputs to ``(kind, url, domain, value)`` targets.

    ``startUrls`` take precedence over ``queries``. ``kind`` is ``search`` for
    query-built and search URLs, ``company`` for a ``/cmp/<slug>/jobs`` URL, or
    ``job`` for a ``/viewjob`` URL; ``value`` is the query, slug or job key.
    """
    if input_model.startUrls:
        out: list[tuple[str, str, str, str]] = []
        for entry in input_model.startUrls:
            resolved = resolve_url(entry.url)
            if resolved is None:
                logger.warning(
                    "[indeed] skipping an unrecognized URL on %s",
                    logged_host(entry.url),
                )
                continue
            out.append((resolved.kind, resolved.url, resolved.domain, resolved.value))
        return out

    domain = None
    urls: list[tuple[str, str, str, str]] = []
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
        urls.append(("search", url, domain, query))
    return urls


# Detail fields that are only on the job page, so they always win over the card.
_DETAIL_ONLY = frozenset({"descriptionHtml", "descriptionText"})


def _blank(value: Any) -> bool:
    """Whether a listing field holds no data (a salary dict counts when empty).

    ``False`` counts too: the detail only reports flags such as ``isRemote``
    when they are set.
    """
    if isinstance(value, dict):
        return all(v in (None, False) for v in value.values())
    return value in (None, "", [], False)


def _merge_detail(item: dict[str, Any], detail: dict[str, Any]) -> None:
    """Merge a job's detail fields (full description, etc.) onto ``item`` in place.

    The detail only fills fields the card left blank (its company link, say,
    carries per-view tracking), except the description. A salary fills per
    subfield: a card may give only its text ('From $20 an hour').
    """
    for key, value in detail.items():
        card = item.get(key)
        if key in _DETAIL_ONLY or _blank(card):
            item[key] = value
        elif isinstance(card, dict) and isinstance(value, dict):
            item[key] = {
                **card,
                **{k: v for k, v in value.items() if card.get(k) is None},
            }


async def _job_item(
    session: IndeedSession, url: str, base_url: str, job_key: str
) -> dict[str, Any] | None:
    """Scrape a single /viewjob URL into an item from its viewjob model alone."""
    model = await session.fetch_job(url, job_key)
    detail = parse_job_detail_model(model, base_url=base_url)
    if not detail:
        return None
    job_key = detail.pop("jobKey", None) or job_key
    return _emit(
        {
            "jobKey": job_key,
            # The canonical link, without the input URL's tracking parameters.
            "jobUrl": f"{base_url}/viewjob?jk={job_key}",
            "source": "indeed",
            **detail,
        }
    )


async def iter_indeed(
    input_model: IndeedScrapeInput, session: IndeedSession
) -> AsyncIterator[dict[str, Any]]:
    """Stream flat job items for every target, deduped by ``jobKey`` across all.

    Targets run concurrently but merge in input order: a target's items are all
    marked seen before the first is yielded, so a later target (which may have
    started already) can only waste a fetch, never emit a duplicate.

    A target sends nothing while the targets before it can still give
    ``maxItems`` (a page counts as ``maxItemsPerQuery``, a job as one), and none
    once they have: it starts only when an earlier one gives short.
    """
    global_seen: set[str] = set()
    targets = _targets(input_model)
    shares = [
        1 if kind == "job" else input_model.maxItemsPerQuery for kind, *_ in targets
    ]
    given: list[int] = []  # fresh items of each merged target, in input order
    merged = asyncio.Condition()

    def needed(index: int) -> bool:
        """Whether the targets before ``index`` may fall short of ``maxItems``."""
        ahead = sum(given) + sum(shares[len(given) : index])
        return ahead < input_model.maxItems

    async def run(
        job: tuple[int, tuple[str, str, str, str]],
    ) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
        index, (kind, url, domain, value) = job
        async with merged:
            await merged.wait_for(lambda: needed(index) or len(given) == index)
        if not needed(index):
            return [], ()
        if kind == "job":
            # A key an earlier target already gave is not fetched; the input key
            # is marked seen too, should the job page name another.
            if value in global_seen:
                return [], ()
            item = await _job_item(session, url, f"https://{domain}", value)
            return ([item], (value,)) if item is not None else ([], ())
        items = await _search_items(
            session,
            url,
            domain=domain,
            max_items=input_model.maxItemsPerQuery,
            company_slug=value if kind == "company" else None,
            details=input_model.scrapeJobDetails,
            seen=global_seen,
        )
        return items, ()

    results = ordered_map(
        enumerate(targets), run, concurrency=_CONCURRENCY, max_ahead=_CONCURRENCY
    )
    async with aclosing(results):
        async for items, aliases in results:
            fresh: list[dict[str, Any]] = []
            for item in items:
                job_key = item.get("jobKey")
                if isinstance(job_key, str):
                    if job_key in global_seen:
                        continue
                    global_seen.add(job_key)
                fresh.append(item)
            global_seen.update(aliases)
            async with merged:
                given.append(len(fresh))
                merged.notify_all()
            for item in fresh:
                yield item


async def scrape_indeed(
    input_model: IndeedScrapeInput,
    *,
    limit: int | None = None,
    session: IndeedSession | None = None,
    on_item: Callable[[int], Awaitable[None]] | None = None,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_indeed` into a list under an optional ``limit``.

    Opens a session when one is not supplied. ``limit`` is a request-time guard,
    not a ceiling baked into the stream. ``on_item`` hears the count after each
    item, for the caller's progress.
    """

    async def _collect(sess: IndeedSession) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        # aclosing: stopping at the limit cancels the targets still running.
        async with aclosing(iter_indeed(input_model, sess)) as stream:
            async for item in stream:
                results.append(item)
                if on_item is not None:
                    await on_item(len(results))
                if limit is not None and len(results) >= limit:
                    break
        return results

    if session is not None:
        return await _collect(session)
    async with open_session() as sess:
        return await _collect(sess)
