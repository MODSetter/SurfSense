"""Orchestrator for the YouTube scraper.

The core is the async generator :func:`iter_youtube` (unbounded / continuation
paged); :func:`scrape_youtube` is a thin collector with a caller-supplied
``limit`` guard. Per-type counters (regular / shorts / streams) are applied
independently per search term and per channel, matching Apify semantics. Any cap
is caller policy, never baked into flow logic.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

from .innertube import (
    INNERTUBE_BROWSE_URL,
    INNERTUBE_NEXT_URL,
    INNERTUBE_PUBLIC_API_KEY,
    INNERTUBE_SEARCH_URL,
    bind_proxy_holder,
    build_innertube_payload,
    fetch_html,
    open_proxy_holder,
    post_innertube,
)
from .parsers import (
    channel_about_tokens,
    extract_yt_initial_data,
    find_first,
    parse_channel_about,
    parse_channel_metadata,
    parse_channel_shorts,
    parse_channel_sort_tokens,
    parse_channel_videos,
    parse_playlist_video_ids,
    parse_search_response,
    parse_translation,
    parse_video_page,
)
from .schemas import VideoItem, YouTubeScrapeInput
from .search_filters import build_search_params
from .subtitles import fetch_subtitles
from .url_resolver import ResolvedUrl, resolve_url

logger = logging.getLogger(__name__)

_SORT_LABELS = {"NEWEST": "Latest", "POPULAR": "Popular", "OLDEST": "Oldest"}

# Independent jobs (one per startUrl / search query / video) run concurrently on
# a pool of warm proxy sessions (sticky IPs). A ramp probe on the gateway ran 64
# parallel flows with zero failures, so the proxy is not the ceiling; 16 workers
# saturate typical job counts while leaving gateway headroom for other callers.
_FANOUT_CONCURRENCY = 16


async def fan_out(
    jobs: list[AsyncIterator[dict[str, Any]]], *, concurrency: int = _FANOUT_CONCURRENCY
) -> AsyncIterator[dict[str, Any]]:
    """Stream items from independent async-iterator jobs via a warm worker pool.

    Each worker opens ONE proxy session and reuses it across the sequential jobs
    it pulls, so only the first job per worker pays the ~2s proxy TCP+TLS
    handshake. A bad job yields nothing rather than aborting the batch; results
    stream out as each job finishes. Workers are cancelled if the consumer stops
    early (e.g. the collector hits its limit).
    """
    if not jobs:
        return
    job_queue: asyncio.Queue[AsyncIterator[dict[str, Any]]] = asyncio.Queue()
    for job in jobs:
        job_queue.put_nowait(job)
    results: asyncio.Queue[list[dict[str, Any]]] = asyncio.Queue()

    async def worker() -> None:
        holder = None
        try:
            holder = await open_proxy_holder()
        except Exception as e:  # no session: jobs still run via one-shot fetches
            logger.warning("[youtube] proxy session open failed: %s", e)
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
                except Exception as e:  # one bad video/URL must not kill the run
                    logger.warning("[youtube] fan-out job failed: %s", e)
                await results.put(items)
        finally:
            if holder is not None:
                await holder.close()

    tasks = [asyncio.create_task(worker()) for _ in range(min(concurrency, len(jobs)))]
    try:
        for _ in range(len(jobs)):
            for item in await results.get():
                yield item
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        # Await cancellation so each worker's finally closes its session before
        # we return — no leaked keep-alive connections when the consumer stops
        # early (e.g. the collector hit its limit).
        await asyncio.gather(*tasks, return_exceptions=True)


async def _post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """POST to InnerTube, retrying with the public web key if keyless fails.

    ponytail: retries with the key only when the keyless call returns nothing;
    could remember which one worked to avoid the extra request.
    """
    data = await post_innertube(url, payload)
    if data is None:
        data = await post_innertube(url, payload, api_key=INNERTUBE_PUBLIC_API_KEY)
    return data


async def _finalize(
    partial: dict[str, Any],
    *,
    input_model: YouTubeScrapeInput,
    source_input: str | None,
    from_url: str | None,
    order: int,
    content_type: str,
) -> dict[str, Any]:
    item = VideoItem(**partial)
    item.type = content_type  # type: ignore[assignment]
    item.input = source_input
    item.fromYTUrl = from_url
    item.order = order
    if input_model.downloadSubtitles and item.id:
        item.subtitles = await fetch_subtitles(
            item.id,
            language=input_model.subtitlesLanguage,
            fmt=input_model.subtitlesFormat,
            prefer_generated=input_model.preferAutoGeneratedSubtitles,
        )
    # translatedTitle/Text: one extra /next in the requested language. ponytail:
    # gated on a non-English subtitlesLanguage so default runs pay nothing; costs
    # one request per item when a translation language is set.
    lang = input_model.subtitlesLanguage
    if item.id and lang and lang != "en":
        data = await _post(
            INNERTUBE_NEXT_URL, build_innertube_payload(video_id=item.id, hl=lang)
        )
        if data:
            item.translatedTitle, item.translatedText = parse_translation(data)
    return item.to_output()


async def _video_flow(
    video_id: str,
    *,
    input_model: YouTubeScrapeInput,
    source_input: str | None,
    from_url: str | None,
    order: int,
    content_type: str,
) -> AsyncIterator[dict[str, Any]]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    html = await fetch_html(url)
    if not html:
        return
    # Watch-page HTML is 1-2MB and the embedded-JSON scan is pure Python; run
    # it off-loop so one video parse can't stall other requests.
    partial = await asyncio.to_thread(parse_video_page, html)
    if not partial:
        return
    yield await _finalize(
        partial,
        input_model=input_model,
        source_input=source_input,
        from_url=from_url,
        order=order,
        content_type=content_type,
    )


async def _search_flow(
    query: str,
    *,
    input_model: YouTubeScrapeInput,
    source_input: str,
) -> AsyncIterator[dict[str, Any]]:
    limit = input_model.maxResults
    if limit <= 0:
        return
    from_url = f"https://www.youtube.com/results?search_query={quote(query)}"
    params = build_search_params(input_model)
    payload = build_innertube_payload(search_query=query, search_params=params)
    data = await _post(INNERTUBE_SEARCH_URL, payload)

    order = 0
    while data:
        items, token = parse_search_response(data)
        for it in items:
            if order >= limit:
                return
            yield await _finalize(
                it,
                input_model=input_model,
                source_input=source_input,
                from_url=from_url,
                order=order,
                content_type="video",
            )
            order += 1
        if not token or order >= limit:
            return
        data = await _post(
            INNERTUBE_SEARCH_URL, build_innertube_payload(continuation_token=token)
        )


def _channel_tab_url(handle: str, tab: str) -> str:
    if handle.startswith("UC") and len(handle) > 10:
        return f"https://www.youtube.com/channel/{handle}/{tab}"
    return f"https://www.youtube.com/@{handle}/{tab}"


# tab path -> (content type, list parser). Streams share the video lockup shape.
_CHANNEL_TABS = {
    "videos": ("video", parse_channel_videos),
    "shorts": ("shorts", parse_channel_shorts),
    "streams": ("stream", parse_channel_videos),
}


async def _fetch_channel_about(initial: dict) -> dict[str, Any]:
    """One ``/browse`` call for the About panel (deep channel fields).

    Panels are unlabeled, so try each engagement token and keep the first that
    returns an ``aboutChannelViewModel``. ponytail: worst case is one extra
    no-op browse before the hit; a labeled-panel signal would remove it.
    """
    for token in channel_about_tokens(initial):
        data = await _post(
            INNERTUBE_BROWSE_URL, build_innertube_payload(continuation_token=token)
        )
        about = find_first(data, "aboutChannelViewModel") if data else None
        if about:
            return parse_channel_about(about)
    return {}


def _published_date(text: str | None):
    """Parse a relative/absolute time string to a ``date`` (best-effort).

    ponytail: channel list pages only expose coarse relative times ("2 years
    ago"), so the ``oldestPostDate`` cutoff is day-accurate at best.
    """
    if not text:
        return None
    import dateparser

    dt = dateparser.parse(text)
    return dt.date() if dt else None


async def _channel_tab_flow(
    handle: str,
    tab: str,
    *,
    limit: int,
    input_model: YouTubeScrapeInput,
    source_input: str,
    channel_meta: dict[str, Any],
    initial: dict | None = None,
    cutoff=None,
) -> AsyncIterator[dict[str, Any]]:
    """Page one channel tab (videos/shorts/streams) up to ``limit`` items.

    Videos honor ``sortVideosBy`` via the sort chips (re-fetch sorted from the
    start); shorts/streams page straight from the seed's first page + its
    continuation, since those tabs don't expose the same sort chips. ``initial``
    may be prefetched (videos tab) to avoid re-downloading the seed.
    """
    if limit <= 0:
        return
    content_type, parse_fn = _CHANNEL_TABS[tab]
    from_url = _channel_tab_url(handle, tab)
    if initial is None:
        seed_html = await fetch_html(from_url)
        if not seed_html:
            return
        initial = await asyncio.to_thread(extract_yt_initial_data, seed_html)
        if not initial:
            return

    # Videos: prefer a sort chip token (fetches page 1 sorted). Otherwise parse
    # the seed's first page directly and follow its continuation.
    items: list[dict[str, Any]] = []
    token: str | None = None
    if tab == "videos":
        tokens = parse_channel_sort_tokens(initial)
        label = _SORT_LABELS.get(input_model.sortVideosBy or "NEWEST", "Latest")
        token = tokens.get(label) or next(iter(tokens.values()), None)
    if token is None:
        items, token = parse_fn(initial)

    order = 0
    while order < limit:
        for it in items:
            if order >= limit:
                return
            # Newest-first ordering: once we pass the cutoff, the rest are older.
            if cutoff is not None:
                item_date = _published_date(it.get("publishedTimeText"))
                if item_date is not None and item_date < cutoff:
                    return
            it.setdefault("channelUsername", handle)
            for key, value in channel_meta.items():
                it.setdefault(key, value)
            yield await _finalize(
                it,
                input_model=input_model,
                source_input=source_input,
                from_url=from_url,
                order=order,
                content_type=content_type,
            )
            order += 1
        if not token:
            return
        data = await _post(
            INNERTUBE_BROWSE_URL, build_innertube_payload(continuation_token=token)
        )
        if not data:
            return
        items, token = parse_fn(data)
        if not items:
            return


async def _channel_flow(
    handle: str,
    *,
    input_model: YouTubeScrapeInput,
    source_input: str,
) -> AsyncIterator[dict[str, Any]]:
    """Scrape a channel's videos, shorts, and streams — each capped independently.

    The videos seed is fetched once and reused to derive channel-wide metadata
    (identity, banner, and the About panel's deep fields) stamped on every item.
    """
    videos_seed = await fetch_html(_channel_tab_url(handle, "videos"))
    initial = (
        await asyncio.to_thread(extract_yt_initial_data, videos_seed)
        if videos_seed
        else None
    )
    channel_meta: dict[str, Any] = {}
    if initial:
        channel_meta = parse_channel_metadata(initial)
        channel_meta.update(await _fetch_channel_about(initial))

    cutoff = _published_date(input_model.oldestPostDate)

    for tab, limit in (
        ("videos", input_model.maxResults),
        ("shorts", input_model.maxResultsShorts),
        ("streams", input_model.maxResultStreams),
    ):
        async for item in _channel_tab_flow(
            handle,
            tab,
            limit=limit,
            input_model=input_model,
            source_input=source_input,
            channel_meta=channel_meta,
            initial=initial if tab == "videos" else None,
            cutoff=cutoff,
        ):
            yield item


async def _playlist_flow(
    playlist_id: str,
    *,
    input_model: YouTubeScrapeInput,
    source_input: str,
) -> AsyncIterator[dict[str, Any]]:
    limit = input_model.maxResults
    if limit <= 0:
        return
    data = await _post(
        INNERTUBE_BROWSE_URL, build_innertube_payload(browse_id=f"VL{playlist_id}")
    )
    # Phase 1: page the playlist for video ids (cheap browse calls, sequential
    # because each continuation depends on the last).
    seen: set[str] = set()
    ordered_ids: list[str] = []
    while data and len(ordered_ids) < limit:
        ids, token = parse_playlist_video_ids(data)
        # A short playlist emits a spurious continuation whose page is empty;
        # stopping on "no new ids" ends both real exhaustion and that loop.
        new_ids = [v for v in ids if v not in seen]
        if not new_ids:
            break
        for vid in new_ids:
            seen.add(vid)
            ordered_ids.append(vid)
            if len(ordered_ids) >= limit:
                break
        if not token:
            break
        data = await _post(
            INNERTUBE_BROWSE_URL, build_innertube_payload(continuation_token=token)
        )

    # Phase 2: resolve the videos concurrently — the per-video watch-page fetch
    # is the bottleneck, so fan them out (each carries its playlist position in
    # ``order``; fan_out emits as they finish, not in playlist order).
    # ponytail: nested fan_out — when many playlist URLs run at once this can
    # stack pools (outer x inner) of proxy sessions. Fine for the common
    # single/few-playlist case; cap inner concurrency if bulk-playlist runs trip it.
    jobs = [
        _video_flow(
            vid,
            input_model=input_model,
            source_input=source_input,
            from_url=source_input,
            order=i,
            content_type="video",
        )
        for i, vid in enumerate(ordered_ids)
    ]
    async for item in fan_out(jobs):
        yield item


async def _hashtag_flow(
    tag: str,
    *,
    input_model: YouTubeScrapeInput,
    source_input: str,
) -> AsyncIterator[dict[str, Any]]:
    """Scrape the dedicated hashtag feed (not a #tag search).

    The hashtag page embeds its feed as ``videoRenderer`` lockups (reused via
    ``parse_search_response``). ponytail: YouTube exposes no continuation for the
    hashtag feed through this path, so it is a single page (~20-35 videos); the
    paging loop is kept for the day a token appears. Upgrade path for more depth:
    fall back to the ``#tag`` search route.
    """
    limit = input_model.maxResults
    if limit <= 0:
        return
    url = f"https://www.youtube.com/hashtag/{quote(tag)}"
    html = await fetch_html(url)
    if not html:
        return
    data = await asyncio.to_thread(extract_yt_initial_data, html)
    order = 0
    while data:
        items, token = parse_search_response(data)
        for it in items:
            if order >= limit:
                return
            yield await _finalize(
                it,
                input_model=input_model,
                source_input=source_input,
                from_url=url,
                order=order,
                content_type="video",
            )
            order += 1
        if not token or order >= limit:
            return
        data = await _post(
            INNERTUBE_BROWSE_URL, build_innertube_payload(continuation_token=token)
        )


async def _dispatch(
    resolved: ResolvedUrl, input_model: YouTubeScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    if resolved.kind == "video":
        content_type = "shorts" if "/shorts/" in resolved.url else "video"
        async for item in _video_flow(
            resolved.value,
            input_model=input_model,
            source_input=resolved.url,
            from_url=resolved.url,
            order=0,
            content_type=content_type,
        ):
            yield item
    elif resolved.kind == "channel":
        async for item in _channel_flow(
            resolved.value, input_model=input_model, source_input=resolved.url
        ):
            yield item
    elif resolved.kind == "playlist":
        async for item in _playlist_flow(
            resolved.value, input_model=input_model, source_input=resolved.url
        ):
            yield item
    elif resolved.kind == "hashtag":
        async for item in _hashtag_flow(
            resolved.value, input_model=input_model, source_input=resolved.url
        ):
            yield item
    elif resolved.kind == "search":
        async for item in _search_flow(
            resolved.value, input_model=input_model, source_input=resolved.url
        ):
            yield item


async def iter_youtube(
    input_model: YouTubeScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield Apify-shaped video items. startUrls override searchQueries.

    Independent startUrls / queries fan out concurrently; each flow's own
    continuation paging stays sequential.
    """
    if input_model.startUrls:
        jobs = []
        for entry in input_model.startUrls:
            resolved = resolve_url(entry.url)
            if not resolved:
                logger.warning("Unrecognized YouTube URL: %s", entry.url)
                continue
            jobs.append(_dispatch(resolved, input_model))
        async for item in fan_out(jobs):
            yield item
        return

    jobs = [
        _search_flow(query, input_model=input_model, source_input=query)
        for query in input_model.searchQueries
    ]
    async for item in fan_out(jobs):
        yield item


async def scrape_youtube(
    input_model: YouTubeScrapeInput, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Collect :func:`iter_youtube` into a list, honoring an optional ``limit``.

    ``limit`` is a request-time policy guard (used by the route), NOT a ceiling
    in the streaming core.
    """
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    async for item in iter_youtube(input_model):
        results.append(item)
        emit_progress("scraping", current=len(results), total=limit, unit="video")
        if limit is not None and len(results) >= limit:
            break
    return results
