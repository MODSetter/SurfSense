"""Orchestrate public Amazon product discovery and enrichment.

The streaming core dispatches each start URL to a product, search, best-sellers,
or shortened-link flow. Network and parsing concerns remain isolated in their
own modules so markup changes and retry policy can be tested independently.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from contextvars import ContextVar
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from proprietary.scraping.concurrency import ordered_map

from .fetch import (
    LocationSession,
    end_call,
    fetch_aod_html,
    fetch_page,
    fetch_seller_html,
    get_location_session,
    no_google_referer,
    resolve_shortlink,
    should_localize,
    start_call,
)
from .locale import accept_language_for, proxy_country_for
from .parsers import (
    is_fallback_product_page,
    parse_aod_offers,
    parse_bestsellers_page,
    parse_product,
    parse_search_page,
    parse_seller,
)
from .schemas import AmazonScrapeInput, ErrorItem, ProductItem
from .url_resolver import ResolvedUrl, resolve_url

__all__ = ["iter_products", "scrape_products"]

logger = logging.getLogger(__name__)

_DETAIL_CONCURRENCY = 8


def _env_int(name: str, default: int) -> int:
    """An integer setting; a malformed value falls back rather than failing import."""
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        logger.warning("Ignoring %s=%r: not an integer", name, os.environ.get(name))
        return default


# AZ-5: a search's details go out in one wave of up to this many (each on its own
# exit, under the process-wide request bound); =8 restores the old two waves.
_DETAIL_WAVE_MAX = _env_int("AMAZON_DETAIL_CONCURRENCY", 16)
# Start URLs and search terms run this many at a time, results kept in order.
_SOURCE_CONCURRENCY = 4
_SEARCH_PAGE_LIMIT = 7
_DEFAULT_ITEMS_PER_START_URL = 100

# Per call: the tool's progress callback, so flows can say which stage they reached.
_on_stage: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar(
    "amazon_on_stage", default=None
)


async def _stage(message: str) -> None:
    report = _on_stage.get()
    if report is not None:
        await report(message)


def _error(
    code: str, description: str, *, input_url: str | None, url: str | None = None
) -> dict[str, Any]:
    return ErrorItem(
        error=code,
        errorDescription=description,
        input=input_url,
        url=url or input_url,
    ).model_dump()


def _buybox_offer(fields: dict[str, Any]) -> dict[str, Any] | None:
    """Synthesize a single offer from the PDP buy box.

    Amazon serves the All-Offers-Display panel as a JS-only modal for many
    (especially US) ASINs, so the AOD ajax endpoint 404s. Fall back to the
    featured buy-box winner already parsed from the product page.
    """
    price = fields.get("price")
    seller = fields.get("seller")
    seller = seller if isinstance(seller, dict) else None
    if not price and not (seller and seller.get("name")):
        return None
    return {
        "position": 1,
        "price": price,
        "condition": fields.get("condition") or "New",
        "delivery": fields.get("delivery"),
        "seller": seller,
        "isPinnedOffer": True,
    }


def _page_url(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page)
    return urlunparse(parsed._replace(query=urlencode(query)))


async def _location_context(
    resolved: ResolvedUrl, input_model: AmazonScrapeInput, route: str
) -> LocationSession | None:
    if (
        not input_model.zipCode
        or not resolved.domain
        or not should_localize(route, input_model.locationDeliverableRoutes)
    ):
        return None
    await _stage("setting the delivery location")
    return await get_location_session(
        resolved.domain,
        zip_code=input_model.zipCode,
        country_code=input_model.countryCode,
        country=proxy_country_for(resolved.marketplace),
        accept_language=accept_language_for(resolved.marketplace),
    )


def _pinned_offer(offers: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            offer
            for offer in offers
            if offer.get("isPinnedOffer") and offer.get("price")
        ),
        None,
    )


async def _product_flow(
    resolved: ResolvedUrl,
    input_model: AmazonScrapeInput,
    *,
    provenance: dict[str, Any] | None = None,
    card: dict[str, Any] | None = None,
    allow_variants: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    """Fetch and enrich one product detail page.

    The offers panel needs only the ASIN, so it is fetched alongside the
    product page, and each seller page starts as soon as its id is known.
    ``card`` is the search or best-seller card the product came from; its price
    stands in when Amazon serves its price-less fallback page.
    """
    asin = resolved.asin
    if not asin or not resolved.domain:
        yield _error(
            "product_not_found",
            "The product URL did not contain a valid ASIN.",
            input_url=resolved.url,
        )
        return

    location = await _location_context(resolved, input_model, "PRODUCT")
    country = proxy_country_for(resolved.marketplace)
    accept_language = accept_language_for(resolved.marketplace)
    domain = resolved.domain
    tasks: list[asyncio.Task[Any]] = []

    async def load_offers() -> list[dict[str, Any]]:
        offer_location = await _location_context(resolved, input_model, "OFFERS")
        html = await fetch_aod_html(
            asin,
            domain,
            country=country,
            accept_language=accept_language,
            location=offer_location or location,
        )
        if not html:
            return []
        return await asyncio.to_thread(parse_aod_offers, html, domain=domain)

    seller_slots = asyncio.Semaphore(_DETAIL_CONCURRENCY)
    seller_tasks: dict[str, asyncio.Task[dict[str, Any] | None]] = {}

    async def load_seller(seller_id: str) -> dict[str, Any] | None:
        async with seller_slots:
            html = await fetch_seller_html(
                seller_id,
                domain,
                country=country,
                accept_language=accept_language,
                location=location,
            )
        if not html:
            return None
        return await asyncio.to_thread(
            parse_seller, html, seller_id=seller_id, domain=domain
        )

    def start_seller(seller: Any) -> None:
        seller_id = seller.get("id") if isinstance(seller, dict) else None
        if input_model.scrapeSellers and seller_id and seller_id not in seller_tasks:
            seller_tasks[seller_id] = asyncio.create_task(load_seller(seller_id))
            tasks.append(seller_tasks[seller_id])

    offers_task = None
    if input_model.maxOffers > 0:
        offers_task = asyncio.create_task(load_offers())
        tasks.append(offers_task)
    try:
        await _stage("fetching product page")
        response = await fetch_page(
            resolved.url,
            country=country,
            accept_language=accept_language,
            stage="pdp",
            location=location,
        )
        if response is None:
            yield _error(
                "product_not_found",
                "The product page could not be loaded after retrying available proxy exits.",
                input_url=resolved.url,
            )
            return
        if response.status in {404, 410}:
            yield _error(
                "product_not_found",
                "The product page was not found.",
                input_url=resolved.url,
            )
            return
        if response.status != 200:
            yield _error(
                "product_not_found",
                f"The product page returned HTTP {response.status}.",
                input_url=resolved.url,
            )
            return

        await _stage("product page fetched")
        fields = await asyncio.to_thread(
            parse_product,
            response.html,
            asin=asin,
            url=response.url,
            domain=domain,
        )
        if not fields.get("title"):
            yield _error(
                "product_not_found",
                "The response did not contain a recognizable product.",
                input_url=resolved.url,
                url=response.url,
            )
            return
        fields.update(provenance or {})
        fields["input"] = resolved.url
        fields["unNormalizedProductUrl"] = resolved.url
        # The session the page really came from: a failed renewal drops the zip.
        loaded = response.location
        fields["locationText"] = loaded.location_text if loaded else None
        fields["loadedCountryCode"] = loaded.country_code if loaded else None
        start_seller(fields.get("seller"))

        # Amazon's cached fallback page has no price, stock or delivery. A card
        # already carries the price; for a product URL the offers panel does.
        fallback = not fields.get("price") and is_fallback_product_page(response.html)
        price_source = "product_page" if fields.get("price") else None
        # Any price-less page takes the card's price, so a marketplace whose
        # fallback page is not recognised still gets one.
        if not fields.get("price") and card is not None and card.get("price"):
            fields["price"] = card["price"]
            fields["listPrice"] = card.get("listPrice")
            price_source = (
                "bestseller_card" if "bestsellerPageData" in card else "search_card"
            )
        elif fallback and card is None and allow_variants and offers_task is None:
            # Top-level product URLs only: a variant fan-out would add one
            # block-prone panel request per variant.
            offers_task = asyncio.create_task(load_offers())
            tasks.append(offers_task)

        offers: list[dict[str, Any]] = await offers_task if offers_task else []
        pinned = _pinned_offer(offers) if fallback and not fields.get("price") else None
        if pinned is not None:
            list_price = pinned.get("listPrice")
            fields["price"] = pinned["price"]
            fields["listPrice"] = (
                list_price
                if list_price and list_price["value"] > pinned["price"]["value"]
                else None
            )
            fields["inStock"] = True
            fields["delivery"] = fields.get("delivery") or pinned.get("delivery")
            price_source = "offers"
        fields["priceSource"] = price_source
        logger.info(
            "[amazon][perf] product asin=%s page=%s cookies=%s price_source=%s",
            asin,
            "fallback" if fallback else "full",
            len(response.cookies),
            price_source,
        )

        if input_model.maxOffers > 0:
            if not offers:
                buybox = _buybox_offer(fields)
                offers = [buybox] if buybox else []
            if offers:
                fields["offers"] = offers[: input_model.maxOffers]

        for offer in fields.get("offers") or []:
            start_seller(offer.get("seller") if isinstance(offer, dict) else None)
        if seller_tasks:
            sellers = await asyncio.gather(*seller_tasks.values())
            by_id = {
                seller["id"]: seller
                for seller in sellers
                if seller and seller.get("id")
            }
            featured = fields.get("seller")
            if isinstance(featured, dict) and featured.get("id") in by_id:
                fields["seller"] = by_id[featured["id"]]
            for offer in fields.get("offers") or []:
                seller = offer.get("seller")
                if isinstance(seller, dict) and seller.get("id") in by_id:
                    offer["seller"] = by_id[seller["id"]]
    finally:
        # Only an early return leaves work in flight; nothing waits on it then.
        for task in tasks:
            task.cancel()

    variant_asins = [
        value for value in fields.get("variantAsins") or [] if value != asin
    ]
    variant_cap = (
        min(len(variant_asins), input_model.maxProductVariantsAsSeparateResults)
        if allow_variants
        else 0
    )
    price_cap = (
        len(variant_asins)
        if allow_variants and input_model.scrapeProductVariantPrices
        else 0
    )
    fetch_count = max(variant_cap, price_cap)
    variant_items: list[dict[str, Any]] = []
    if fetch_count:

        async def load_variant(variant_asin: str) -> list[dict[str, Any]]:
            variant_url = f"https://{resolved.domain}/dp/{variant_asin}"
            variant_resolved = resolve_url(variant_url)
            if variant_resolved is None:
                return []
            return [
                item
                async for item in _product_flow(
                    variant_resolved, input_model, allow_variants=False
                )
            ]

        variant_items = [
            item
            async for batch in ordered_map(
                variant_asins[:fetch_count],
                load_variant,
                concurrency=_DETAIL_CONCURRENCY,
            )
            for item in batch
            if "error" not in item
        ]
        if input_model.scrapeProductVariantPrices:
            prices = {
                item.get("asin"): item.get("price")
                for item in variant_items
                if item.get("asin")
            }
            details = fields.get("variantDetails") or [
                {"asin": variant_asin} for variant_asin in variant_asins
            ]
            for detail in details:
                if detail.get("asin") in prices:
                    detail["price"] = prices[detail["asin"]]
            fields["variantDetails"] = details

    yield ProductItem(**fields).to_output()
    for item in variant_items[:variant_cap]:
        item["originalAsin"] = asin
        yield item


def _new_cards(cards: list[dict[str, Any]], seen: set[str]) -> list[dict[str, Any]]:
    """Drop cards whose ASIN was already taken, on this page or an earlier one."""
    fresh: list[dict[str, Any]] = []
    for card in cards:
        asin = card.get("asin")
        if asin and asin not in seen:
            seen.add(asin)
            fresh.append(card)
    return fresh


def _card_product(card: dict[str, Any], domain: str) -> ResolvedUrl | None:
    """The product page for a card, or its plain /dp/ page when the link is not one."""
    product = resolve_url(card["url"])
    if product is None or product.kind != "product" or product.asin != card["asin"]:
        product = resolve_url(f"https://{domain}/dp/{card['asin']}")
    return product


async def _card_details(
    cards: list[dict[str, Any]],
    remaining: int,
    load_card: Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]],
) -> AsyncIterator[dict[str, Any]]:
    """Load a page's cards in waves until ``remaining`` products came back.

    A failed detail does not count, so the next wave takes this page's next
    cards instead of the flow moving on to another (block-prone) page. Items
    are yielded in card order as soon as they and the cards before them are done.
    """
    cursor = 0
    while cursor < len(cards) and remaining > 0:
        wave = cards[cursor : cursor + remaining]
        cursor += len(wave)
        concurrency = min(len(wave), max(1, _DETAIL_WAVE_MAX))
        async with aclosing(
            ordered_map(wave, load_card, concurrency=concurrency)
        ) as batches:
            async for batch in batches:
                for item in batch:
                    if "error" not in item:
                        if remaining <= 0:
                            return
                        remaining -= 1
                    yield item


async def _search_flow(
    resolved: ResolvedUrl, input_model: AmazonScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Page through search results and optionally fetch product details."""
    if not resolved.domain:
        yield _error(
            "no_results_found", "The search domain was invalid.", input_url=resolved.url
        )
        return
    domain = resolved.domain
    cap = (
        input_model.maxItemsPerStartUrl
        if input_model.maxItemsPerStartUrl is not None
        else _DEFAULT_ITEMS_PER_START_URL
    )
    max_pages = min(input_model.maxSearchPagesPerStartUrl, _SEARCH_PAGE_LIMIT)
    location = await _location_context(resolved, input_model, "SEARCH")
    country = proxy_country_for(resolved.marketplace)
    accept_language = accept_language_for(resolved.marketplace)
    seen: set[str] = set()
    emitted = 0
    parsed = 0

    async def load_card(card: dict[str, Any]) -> list[dict[str, Any]]:
        product = _card_product(card, domain)
        if product is None:
            return []
        provenance = {"categoryPageData": card["categoryPageData"]}
        return [
            item
            async for item in _product_flow(
                product, input_model, provenance=provenance, card=card
            )
        ]

    for page in range(1, max_pages + 1):
        await _stage(f"fetching search page {page}")
        html_response = await fetch_page(
            _page_url(resolved.url, page),
            country=country,
            accept_language=accept_language,
            google_referer=not no_google_referer(),
            stage="search",
            location=location,
        )
        cards = (
            await asyncio.to_thread(
                parse_search_page,
                html_response.html,
                page=page,
                domain=domain,
                offset=parsed,
            )
            if html_response is not None and html_response.status == 200
            else []
        )
        parsed += len(cards)
        cards = _new_cards(cards, seen)
        if not cards:
            if page == 1:
                yield _error(
                    "no_results_found",
                    "The search page did not contain any products.",
                    input_url=resolved.url,
                )
            return
        if input_model.scrapeProductDetails is False:
            for card in cards[: max(0, cap - emitted)]:
                card["input"] = resolved.url
                yield ProductItem(**card).to_output()
                emitted += 1
        else:
            async with aclosing(
                _card_details(cards, cap - emitted, load_card)
            ) as details:
                async for item in details:
                    yield item
                    if "error" not in item:
                        emitted += 1
        if emitted >= cap:
            return


async def _bestsellers_flow(
    resolved: ResolvedUrl, input_model: AmazonScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Page through a best-sellers category and emit ranked products."""
    if not resolved.domain:
        yield _error(
            "bestsellers_category_not_found",
            "The best-sellers domain was invalid.",
            input_url=resolved.url,
        )
        return
    domain = resolved.domain
    cap = (
        input_model.maxItemsPerStartUrl
        if input_model.maxItemsPerStartUrl is not None
        else _DEFAULT_ITEMS_PER_START_URL
    )
    country = proxy_country_for(resolved.marketplace)
    accept_language = accept_language_for(resolved.marketplace)
    seen: set[str] = set()
    emitted = 0

    async def load_card(card: dict[str, Any]) -> list[dict[str, Any]]:
        product = _card_product(card, domain)
        if product is None:
            return []
        return [
            item
            async for item in _product_flow(
                product,
                input_model,
                provenance={"bestsellerPageData": card["bestsellerPageData"]},
                card=card,
            )
        ]

    for page in range(1, min(input_model.maxSearchPagesPerStartUrl, 2) + 1):
        await _stage(f"fetching best-sellers page {page}")
        response = await fetch_page(
            _page_url(resolved.url, page),
            country=country,
            accept_language=accept_language,
            google_referer=not no_google_referer(),
            stage="bestsellers",
        )
        cards = (
            await asyncio.to_thread(
                parse_bestsellers_page,
                response.html,
                page=page,
                domain=domain,
            )
            if response is not None and response.status == 200
            else []
        )
        cards = _new_cards(cards, seen)
        if not cards:
            if page == 1:
                yield _error(
                    "bestsellers_category_not_found",
                    "The page did not contain a recognizable best-sellers category.",
                    input_url=resolved.url,
                )
            return
        if input_model.scrapeProductDetails is False:
            for card in cards[: max(0, cap - emitted)]:
                card["input"] = resolved.url
                yield ProductItem(**card).to_output()
                emitted += 1
        else:
            async with aclosing(
                _card_details(cards, cap - emitted, load_card)
            ) as details:
                async for item in details:
                    yield item
                    if "error" not in item:
                        emitted += 1
        if emitted >= cap:
            return


async def _shortened_flow(
    resolved: ResolvedUrl, input_model: AmazonScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Resolve a shortened link and dispatch its final Amazon URL."""
    target = await resolve_shortlink(resolved.url)
    final = resolve_url(target) if target else None
    if final is None or final.kind == "shortened":
        yield _error(
            "shortened_url_invalid",
            "The shortened link did not resolve to a supported Amazon page.",
            input_url=resolved.url,
            url=target,
        )
        return
    async for item in _FLOWS[final.kind](final, input_model):
        if "input" in item:
            item["input"] = resolved.url
        yield item


_FLOWS = {
    "product": _product_flow,
    "search": _search_flow,
    "bestsellers": _bestsellers_flow,
    "shortened": _shortened_flow,
}


async def _source_items(
    entry: Any, input_model: AmazonScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    url = entry.get("url") if isinstance(entry, dict) else None
    resolved = resolve_url(url) if url else None
    if resolved is None:
        yield _error(
            "invalid_url",
            "Start URL was malformed or not a recognized Amazon URL.",
            input_url=url,
        )
        return
    async with aclosing(_FLOWS[resolved.kind](resolved, input_model)) as items:
        async for item in items:
            yield item


async def iter_products(
    input_model: AmazonScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield product items for every start URL.

    Each ``categoryOrProductUrls`` entry is classified and dispatched to its
    per-kind flow. A URL that cannot be recognized as an Amazon product /
    search / bestsellers / shortened link yields an ``invalid_url`` error item
    (the failure model is in-stream error items, not exceptions). Several
    entries run a few at a time and their items come out in input order.
    """
    entries = list(input_model.categoryOrProductUrls)
    if len(entries) == 1:
        async with aclosing(_source_items(entries[0], input_model)) as items:
            async for item in items:
                yield item
        return

    async def collect(entry: Any) -> list[dict[str, Any]]:
        return [item async for item in _source_items(entry, input_model)]

    async with aclosing(
        ordered_map(entries, collect, concurrency=_SOURCE_CONCURRENCY)
    ) as batches:
        async for batch in batches:
            for item in batch:
                yield item


async def scrape_products(
    input_model: AmazonScrapeInput,
    *,
    limit: int | None = None,
    on_item: Callable[[int], Awaitable[None]] | None = None,
    on_stage: Callable[[str], Awaitable[None]] | None = None,
    notes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Collect :func:`iter_products` into a list, honoring an optional ``limit``.

    ``limit`` is a request-time policy guard, NOT a ceiling in the streaming
    core. ``on_item`` hears the count after each item and ``on_stage`` each
    stage reached, for the caller's progress. ``notes`` receives what the call
    could not honour, such as a zip code Amazon would not apply.
    """
    results: list[dict[str, Any]] = []
    call_notes, hedges_token, notes_token = start_call()
    stage_token = _on_stage.set(on_stage)
    try:
        async with aclosing(iter_products(input_model)) as items:
            async for item in items:
                results.append(item)
                if on_item is not None:
                    await on_item(len(results))
                if limit is not None and len(results) >= limit:
                    break
    finally:
        _on_stage.reset(stage_token)
        end_call(hedges_token, notes_token)
    if notes is not None:
        notes.extend(call_notes)
    return results
