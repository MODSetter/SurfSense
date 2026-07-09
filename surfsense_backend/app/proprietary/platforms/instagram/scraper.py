"""Orchestrator for the Instagram scraper.

The core is the async generator :func:`iter_instagram` (unbounded);
:func:`scrape_instagram` is a thin collector with a caller-supplied ``limit``
guard. Any cap is caller policy, never baked into flow logic.

Independent targets (one per ``directUrl`` / discovered entity) fan out
concurrently on a pool of warm sessions (sticky IPs); each target's own paging
stays sequential. ``fan_out`` is ported from ``../reddit/scraper.py`` but bound
to *this* module's proxy holders so every worker warms its own session once and
reuses it.

Flows are selected by ``resultsType``:
- ``posts`` / ``reels`` / ``mentions`` -> media items (profile / hashtag feeds,
  or discovery search)
- ``comments`` -> comment items for post/reel URLs
- ``details`` -> profile / hashtag / place metadata (by URL or discovery search)

ponytail: deep feed pagination (past the first web page of media) needs the
GraphQL cursor endpoint whose doc-id drifts; v1 emits the first page and stops.
The upgrade path is a ``_paginate_feed`` helper in this file plus a doc-id in
``fetch.py`` — contained to these two files, per the acquisition-seam rule.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from datetime import UTC, datetime, timedelta
from typing import Any

from .fetch import (
    InstagramAccessBlockedError,
    bind_proxy_holder,
    fetch_json,
    now_iso,
    open_proxy_holder,
)
from .parsers import (
    parse_comment,
    parse_hashtag,
    parse_media,
    parse_place,
    parse_profile,
)
from .schemas import InstagramScrapeInput
from .url_resolver import ResolvedUrl, resolve_url

logger = logging.getLogger(__name__)

__all__ = [
    "InstagramAccessBlockedError",
    "iter_instagram",
    "scrape_instagram",
]

# Independent jobs run concurrently on a pool of warm proxy sessions. Anonymous
# Instagram is the most hostile platform, so this stays low to avoid burning the
# residential pool with parallel login walls.
_FANOUT_CONCURRENCY = 8

# Per-post comment fetches fan across their own warm sessions; kept below the
# top-level width so N concurrent targets x this can't explode the IP count.
_COMMENT_CONCURRENCY = 4

_PROFILE_PATH = "api/v1/users/web_profile_info/"
_HASHTAG_PATH = "api/v1/tags/web_info/"
_LOCATION_PATH = "api/v1/locations/web_info/"
_SEARCH_PATH = "web/search/topsearch/"


def _parse_newer_than(value: str | None) -> datetime | None:
    """Parse ``onlyPostsNewerThan`` (ISO, YYYY-MM-DD, or relative) to UTC.

    Relative forms: ``"<n> <unit>"`` where unit is minute/hour/day/week/month/
    year (singular or plural). Anything unparseable returns ``None`` (no filter).
    """
    if not value:
        return None
    text = value.strip().lower()
    parts = text.split()
    if len(parts) == 2 and parts[0].isdigit():
        n = int(parts[0])
        unit = parts[1].rstrip("s")
        days = {
            "minute": n / 1440,
            "hour": n / 24,
            "day": n,
            "week": n * 7,
            "month": n * 30,
            "year": n * 365,
        }.get(unit)
        if days is None:
            return None
        return datetime.now(UTC) - timedelta(days=days)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo:
            return dt
        return dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def _is_after(timestamp: str | None, cutoff: datetime | None) -> bool:
    """True if the item ``timestamp`` (ISO) is at/after the cutoff (or no cutoff)."""
    if cutoff is None:
        return True
    if not timestamp:
        return True
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt >= cutoff
    except ValueError:
        return True


async def fan_out(
    jobs: list[AsyncIterator[dict[str, Any]]], *, concurrency: int = _FANOUT_CONCURRENCY
) -> AsyncIterator[dict[str, Any]]:
    """Stream items from independent async-iterator jobs via a warm worker pool.

    Each worker opens ONE proxy session and reuses it across the sequential jobs
    it pulls, so only the first job per worker pays the proxy handshake + the
    cookie warm-up. Partial results (matches the reddit sibling): one blocked or
    failed target yields nothing rather than aborting the batch — Instagram is
    an aggregation, not an atomic transaction, so 4/5 good targets beat 0/5. But
    if EVERY target was refused (zero items AND a hard block seen), the whole run
    couldn't reach anonymous data, so we surface ``InstagramAccessBlockedError``
    (-> 403) instead of a misleading empty success. Workers are cancelled and
    their sessions closed if the consumer stops early.
    """
    if not jobs:
        return
    job_queue: asyncio.Queue[AsyncIterator[dict[str, Any]]] = asyncio.Queue()
    for job in jobs:
        job_queue.put_nowait(job)
    results: asyncio.Queue[list[dict[str, Any]]] = asyncio.Queue()
    blocked = False  # set if any target hit a hard login/auth wall

    async def worker() -> None:
        nonlocal blocked
        holder = None
        try:
            holder = await open_proxy_holder()
        except Exception as e:  # no session: jobs still run via one-shot fetches
            logger.warning("[instagram] proxy session open failed: %s", e)
        try:
            while True:
                try:
                    job = job_queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                items: list[dict[str, Any]] = []
                try:
                    if holder is not None:
                        async with bind_proxy_holder(holder):
                            items = [item async for item in job]
                    else:
                        items = [item async for item in job]
                except InstagramAccessBlockedError as e:
                    # Partial results: a blocked target must not kill the batch.
                    # Record it so a fully-blocked run can still surface the 403.
                    blocked = True
                    logger.warning("[instagram] target blocked: %s", e)
                except Exception as e:  # one bad target must not kill the run
                    logger.warning("[instagram] fan-out job failed: %s", e)
                await results.put(items)
        finally:
            if holder is not None:
                await holder.close()

    tasks = [asyncio.create_task(worker()) for _ in range(min(concurrency, len(jobs)))]
    emitted = 0
    try:
        for _ in range(len(jobs)):
            for item in await results.get():
                emitted += 1
                yield item
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    # Reached only on natural exhaustion (an early-stop close raises GeneratorExit
    # inside the loop and skips this). Nothing came back AND a wall was hit ->
    # the run was fully refused, so fail loud rather than return empty.
    if emitted == 0 and blocked:
        raise InstagramAccessBlockedError(
            "Instagram refused anonymous access to every target"
        )


def _emit(partial: dict[str, Any], *, input_url: str | None) -> dict[str, Any]:
    """Stamp provenance and serialize (parsers return plain dicts)."""
    out = {**partial, "scrapedAt": now_iso()}
    if input_url is not None:
        out.setdefault("inputUrl", input_url)
    return out


async def _profile_user(username: str) -> dict[str, Any] | None:
    """Fetch a profile's ``data.user`` node, or ``None``."""
    data = await fetch_json(_PROFILE_PATH, {"username": username})
    if isinstance(data, dict):
        user = (
            data.get("data", {}).get("user")
            if isinstance(data.get("data"), dict)
            else None
        )
        if isinstance(user, dict):
            return user
        return None
    return None


def _media_matches(item: dict[str, Any], result_type: str) -> bool:
    """Filter a media item by feed type. ``reels`` keeps clips/videos only."""
    if result_type == "reels":
        return item.get("type") == "Video" or item.get("productType") == "clips"
    return True


async def _media_flow(
    resolved: ResolvedUrl,
    *,
    input_model: InstagramScrapeInput,
    cutoff: datetime | None,
    per_target: int,
) -> AsyncIterator[dict[str, Any]]:
    """Emit media items for a profile / hashtag / place URL."""
    from .parsers import _edges

    result_type = input_model.resultsType
    if resolved.kind == "profile":
        user = await _profile_user(resolved.value)
        if user is None:
            return
        nodes = _edges(user.get("edge_owner_to_timeline_media"))
        emitted = 0
        for node in nodes:
            item = parse_media(node)
            if input_model.skipPinnedPosts and item.get("isPinned"):
                continue
            if not _media_matches(item, result_type):
                continue
            if not _is_after(item.get("timestamp"), cutoff):
                continue
            yield _emit(item, input_url=resolved.url)
            emitted += 1
            if emitted >= per_target:
                return
        return
    if resolved.kind == "hashtag":
        data = await fetch_json(_HASHTAG_PATH, {"tag_name": resolved.value})
        if isinstance(data, dict):
            parsed = parse_hashtag(data)
            emitted = 0
            for node in [*parsed.get("topPosts", []), *parsed.get("posts", [])]:
                if not _media_matches(node, result_type):
                    continue
                if not _is_after(node.get("timestamp"), cutoff):
                    continue
                yield _emit(node, input_url=resolved.url)
                emitted += 1
                if emitted >= per_target:
                    return
        return
    if resolved.kind == "place":
        data = await fetch_json(_LOCATION_PATH, {"location_id": resolved.value})
        if isinstance(data, dict):
            parsed = parse_place(data)
            emitted = 0
            for node in parsed.get("posts", []):
                if not _is_after(node.get("timestamp"), cutoff):
                    continue
                yield _emit(node, input_url=resolved.url)
                emitted += 1
                if emitted >= per_target:
                    return
        return


async def _comments_flow(
    resolved: ResolvedUrl,
    *,
    input_model: InstagramScrapeInput,
    per_target: int,
) -> AsyncIterator[dict[str, Any]]:
    """Emit comment items for a post / reel URL.

    ponytail: the anonymous comment page uses a GraphQL cursor whose doc-id
    drifts; v1 sources the comments embedded in the media info payload and caps
    at the actor's 50/post ceiling. Deeper paging is the upgrade path in
    ``fetch.py``.
    """
    from .parsers import _edges

    path = f"p/{resolved.value}/"
    data = await fetch_json(path, {"__a": 1, "__d": "dis"})
    node = None
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list) and items:
            node = items[0]
        else:
            gql = data.get("graphql")
            node = gql.get("shortcode_media") if isinstance(gql, dict) else None
    if not isinstance(node, dict):
        return
    comment_nodes = _edges(node.get("edge_media_to_parent_comment")) or _edges(
        node.get("edge_media_to_comment")
    )
    cap = min(per_target, 50)
    emitted = 0
    for cnode in comment_nodes:
        item = parse_comment(cnode, post_url=resolved.url)
        yield _emit(item, input_url=resolved.url)
        emitted += 1
        if input_model.includeNestedComments:
            for reply in _edges(cnode.get("edge_threaded_comments")):
                if emitted >= cap:
                    return
                yield _emit(
                    parse_comment(reply, post_url=resolved.url),
                    input_url=resolved.url,
                )
                emitted += 1
        if emitted >= cap:
            return


async def _details_flow(
    resolved: ResolvedUrl, *, input_model: InstagramScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Emit one profile / hashtag / place detail item for a URL."""
    if resolved.kind == "profile":
        user = await _profile_user(resolved.value)
        if user is not None:
            yield _emit(parse_profile(user), input_url=resolved.url)
        return
    if resolved.kind == "hashtag":
        data = await fetch_json(_HASHTAG_PATH, {"tag_name": resolved.value})
        if isinstance(data, dict):
            yield _emit(parse_hashtag(data), input_url=resolved.url)
        return
    if resolved.kind == "place":
        data = await fetch_json(_LOCATION_PATH, {"location_id": resolved.value})
        if isinstance(data, dict):
            yield _emit(parse_place(data), input_url=resolved.url)
        return


async def _discover(
    query: str, *, search_type: str, limit: int
) -> list[ResolvedUrl]:
    """Resolve a discovery query into target URLs via topsearch."""
    data = await fetch_json(_SEARCH_PATH, {"query": query, "context": "blended"})
    if not isinstance(data, dict):
        return []
    out: list[ResolvedUrl] = []
    if search_type in ("profile", "user"):
        for entry in data.get("users", []):
            user = entry.get("user", {}) if isinstance(entry, dict) else {}
            name = user.get("username")
            if not name:
                continue
            out.append(
                ResolvedUrl("profile", name, f"https://www.instagram.com/{name}/")
            )
    elif search_type == "hashtag":
        for entry in data.get("hashtags", []):
            tag = entry.get("hashtag", {}) if isinstance(entry, dict) else {}
            name = tag.get("name")
            if not name:
                continue
            out.append(
                ResolvedUrl(
                    "hashtag",
                    name,
                    f"https://www.instagram.com/explore/tags/{name}/",
                )
            )
    elif search_type == "place":
        for entry in data.get("places", []):
            place = entry.get("place", {}) if isinstance(entry, dict) else {}
            loc = place.get("location", {}) if isinstance(place, dict) else {}
            pk = loc.get("pk") or loc.get("id")
            if not pk:
                continue
            out.append(
                ResolvedUrl(
                    "place",
                    str(pk),
                    f"https://www.instagram.com/explore/locations/{pk}/",
                )
            )
    return out[:limit]


def _resolve_inputs(input_model: InstagramScrapeInput) -> list[ResolvedUrl]:
    """Resolve ``directUrls`` (URLs take priority over ``search``)."""
    resolved: list[ResolvedUrl] = []
    for url in input_model.directUrls:
        r = resolve_url(url)
        if r is None:
            logger.warning("[instagram] unrecognized URL: %s", url)
            continue
        resolved.append(r)
    return resolved


async def _targets(input_model: InstagramScrapeInput) -> list[ResolvedUrl]:
    """The resolved targets for this run: direct URLs, else discovery search."""
    if input_model.directUrls:
        return _resolve_inputs(input_model)
    if not input_model.search:
        return []
    limit = input_model.searchLimit or 10
    queries = [q.strip() for q in input_model.search.split(",") if q.strip()]
    targets: list[ResolvedUrl] = []
    for query in queries:
        targets.extend(
            await _discover(query, search_type=input_model.searchType, limit=limit)
        )
    return targets


async def iter_instagram(
    input_model: InstagramScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield flat Instagram items. ``directUrls`` override ``search``.

    Independent targets fan out concurrently; each target's paging stays
    sequential. De-dupes media by ``id`` across targets.
    """
    targets = await _targets(input_model)
    if not targets:
        return
    result_type = input_model.resultsType
    cutoff = _parse_newer_than(input_model.onlyPostsNewerThan)
    per_target = input_model.resultsLimit or 10

    if result_type == "comments":
        jobs = [
            _comments_flow(r, input_model=input_model, per_target=per_target)
            for r in targets
            if r.kind in ("post", "reel")
        ]
        async with aclosing(fan_out(jobs, concurrency=_COMMENT_CONCURRENCY)) as stream:
            async for item in stream:
                yield item
        return

    if result_type == "details":
        jobs = [_details_flow(r, input_model=input_model) for r in targets]
        async with aclosing(fan_out(jobs)) as stream:
            async for item in stream:
                yield item
        return

    # posts / reels / mentions -> media feeds, de-duped by id across targets.
    jobs = [
        _media_flow(
            r, input_model=input_model, cutoff=cutoff, per_target=per_target
        )
        for r in targets
    ]
    seen: set[str] = set()
    async with aclosing(fan_out(jobs)) as stream:
        async for item in stream:
            item_id = item.get("id")
            if isinstance(item_id, str):
                if item_id in seen:
                    continue
                seen.add(item_id)
            yield item


async def scrape_instagram(
    input_model: InstagramScrapeInput, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Collect :func:`iter_instagram` into a list, honoring an optional ``limit``.

    ``limit`` is a request-time policy guard, NOT a ceiling in the streaming
    core.
    """
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    async with aclosing(iter_instagram(input_model)) as stream:
        async for item in stream:
            results.append(item)
            emit_progress("scraping", current=len(results), total=limit, unit="item")
            if limit is not None and len(results) >= limit:
                break
    return results
