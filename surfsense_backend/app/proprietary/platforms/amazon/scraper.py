"""Orchestrate public Amazon product discovery and enrichment.

The streaming core dispatches each start URL to a product, search, best-sellers,
or shortened-link flow. Network and parsing concerns remain isolated in their
own modules so markup changes and retry policy can be tested independently.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .fetch import (
    fetch_aod_html,
    fetch_page,
    fetch_seller_html,
    gather_bounded,
    get_location_session,
    resolve_shortlink,
    should_localize,
)
from .locale import accept_language_for, proxy_country_for
from .parsers import (
    parse_aod_offers,
    parse_bestsellers_page,
    parse_product,
    parse_search_page,
    parse_seller,
)
from .schemas import AmazonScrapeInput, ErrorItem, ProductItem
from .url_resolver import ResolvedUrl, resolve_url

__all__ = ["iter_products", "scrape_products"]

_DETAIL_CONCURRENCY = 8
_SEARCH_PAGE_LIMIT = 7
_DEFAULT_ITEMS_PER_START_URL = 100


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
) -> tuple[dict[str, str] | None, str | None, str | None, str | None]:
    if (
        not input_model.zipCode
        or not resolved.domain
        or not should_localize(route, input_model.locationDeliverableRoutes)
    ):
        return None, None, None, None
    session = await get_location_session(
        resolved.domain,
        zip_code=input_model.zipCode,
        country_code=input_model.countryCode,
        country=proxy_country_for(resolved.marketplace),
        accept_language=accept_language_for(resolved.marketplace),
    )
    if session is None:
        return None, None, None, None
    return (
        session.cookies,
        session.proxy,
        session.location_text,
        session.country_code,
    )


async def _product_flow(
    resolved: ResolvedUrl,
    input_model: AmazonScrapeInput,
    *,
    provenance: dict[str, Any] | None = None,
    allow_variants: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    """Fetch and enrich one product detail page."""
    asin = resolved.asin
    if not asin or not resolved.domain:
        yield _error(
            "product_not_found",
            "The product URL did not contain a valid ASIN.",
            input_url=resolved.url,
        )
        return

    cookies, proxy, location_text, loaded_country = await _location_context(
        resolved, input_model, "PRODUCT"
    )
    country = proxy_country_for(resolved.marketplace)
    accept_language = accept_language_for(resolved.marketplace)
    response = await fetch_page(
        resolved.url,
        cookies=cookies,
        proxy=proxy,
        country=country,
        accept_language=accept_language,
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

    fields = await asyncio.to_thread(
        parse_product,
        response.html,
        asin=asin,
        url=response.url,
        domain=resolved.domain,
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
    fields["locationText"] = location_text
    fields["loadedCountryCode"] = loaded_country

    if input_model.maxOffers > 0:
        offer_cookies, offer_proxy, _, _ = await _location_context(
            resolved, input_model, "OFFERS"
        )
        offers_html = await fetch_aod_html(
            asin,
            resolved.domain,
            cookies=offer_cookies or cookies,
            proxy=offer_proxy or proxy,
            country=country,
            accept_language=accept_language,
        )
        offers = (
            parse_aod_offers(offers_html, domain=resolved.domain) if offers_html else []
        )
        if not offers:
            buybox = _buybox_offer(fields)
            offers = [buybox] if buybox else []
        if offers:
            fields["offers"] = offers[: input_model.maxOffers]

    if input_model.scrapeSellers:
        seller_ids: list[str] = []
        featured = fields.get("seller")
        if isinstance(featured, dict) and featured.get("id"):
            seller_ids.append(featured["id"])
        for offer in fields.get("offers") or []:
            seller = offer.get("seller") if isinstance(offer, dict) else None
            if isinstance(seller, dict) and seller.get("id"):
                seller_ids.append(seller["id"])
        seller_ids = list(dict.fromkeys(seller_ids))

        async def load_seller(seller_id: str) -> dict[str, Any] | None:
            html = await fetch_seller_html(
                seller_id,
                resolved.domain,
                cookies=cookies,
                proxy=proxy,
                country=country,
                accept_language=accept_language,
            )
            return (
                parse_seller(html, seller_id=seller_id, domain=resolved.domain)
                if html
                else None
            )

        sellers = await gather_bounded(
            [
                lambda seller_id=seller_id: load_seller(seller_id)
                for seller_id in seller_ids
            ],
            concurrency=_DETAIL_CONCURRENCY,
        )
        by_id = {
            seller["id"]: seller for seller in sellers if seller and seller.get("id")
        }
        if featured and featured.get("id") in by_id:
            fields["seller"] = by_id[featured["id"]]
        for offer in fields.get("offers") or []:
            seller = offer.get("seller")
            if isinstance(seller, dict) and seller.get("id") in by_id:
                offer["seller"] = by_id[seller["id"]]

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

        batches = await gather_bounded(
            [
                lambda variant_asin=variant_asin: load_variant(variant_asin)
                for variant_asin in variant_asins[:fetch_count]
            ],
            concurrency=_DETAIL_CONCURRENCY,
        )
        variant_items = [
            item for batch in batches for item in batch if "error" not in item
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


async def _search_flow(
    resolved: ResolvedUrl, input_model: AmazonScrapeInput
) -> AsyncIterator[dict[str, Any]]:
    """Page through search results and optionally fetch product details."""
    if not resolved.domain:
        yield _error(
            "no_results_found", "The search domain was invalid.", input_url=resolved.url
        )
        return
    cap = (
        input_model.maxItemsPerStartUrl
        if input_model.maxItemsPerStartUrl is not None
        else _DEFAULT_ITEMS_PER_START_URL
    )
    max_pages = min(input_model.maxSearchPagesPerStartUrl, _SEARCH_PAGE_LIMIT)
    cookies, proxy, _, _ = await _location_context(resolved, input_model, "SEARCH")
    country = proxy_country_for(resolved.marketplace)
    accept_language = accept_language_for(resolved.marketplace)
    seen: set[str] = set()
    emitted = 0
    for page in range(1, max_pages + 1):
        html_response = await fetch_page(
            _page_url(resolved.url, page),
            cookies=cookies,
            proxy=proxy,
            country=country,
            accept_language=accept_language,
        )
        cards = (
            await asyncio.to_thread(
                parse_search_page,
                html_response.html,
                page=page,
                domain=resolved.domain,
            )
            if html_response is not None and html_response.status == 200
            else []
        )
        cards = [
            card for card in cards if card.get("asin") and card["asin"] not in seen
        ]
        for card in cards:
            seen.add(card["asin"])
        if not cards:
            if page == 1:
                yield _error(
                    "no_results_found",
                    "The search page did not contain any products.",
                    input_url=resolved.url,
                )
            return
        cards = cards[: max(0, cap - emitted)]
        if input_model.scrapeProductDetails is False:
            for card in cards:
                card["input"] = resolved.url
                yield ProductItem(**card).to_output()
                emitted += 1
        else:

            async def load_card(card: dict[str, Any]) -> list[dict[str, Any]]:
                product = resolve_url(card["url"])
                if product is None:
                    return []
                provenance = {"categoryPageData": card["categoryPageData"]}
                return [
                    item
                    async for item in _product_flow(
                        product, input_model, provenance=provenance
                    )
                ]

            batches = await gather_bounded(
                [lambda card=card: load_card(card) for card in cards],
                concurrency=_DETAIL_CONCURRENCY,
            )
            for batch in batches:
                for item in batch:
                    if "error" not in item and emitted >= cap:
                        return
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
    cap = (
        input_model.maxItemsPerStartUrl
        if input_model.maxItemsPerStartUrl is not None
        else _DEFAULT_ITEMS_PER_START_URL
    )
    country = proxy_country_for(resolved.marketplace)
    accept_language = accept_language_for(resolved.marketplace)
    seen: set[str] = set()
    emitted = 0
    for page in range(1, min(input_model.maxSearchPagesPerStartUrl, 2) + 1):
        response = await fetch_page(
            _page_url(resolved.url, page),
            country=country,
            accept_language=accept_language,
        )
        cards = (
            await asyncio.to_thread(
                parse_bestsellers_page,
                response.html,
                page=page,
                domain=resolved.domain,
            )
            if response is not None and response.status == 200
            else []
        )
        cards = [
            card for card in cards if card.get("asin") and card["asin"] not in seen
        ]
        for card in cards:
            seen.add(card["asin"])
        if not cards:
            if page == 1:
                yield _error(
                    "bestsellers_category_not_found",
                    "The page did not contain a recognizable best-sellers category.",
                    input_url=resolved.url,
                )
            return
        cards = cards[: max(0, cap - emitted)]
        if input_model.scrapeProductDetails is False:
            for card in cards:
                card["input"] = resolved.url
                yield ProductItem(**card).to_output()
                emitted += 1
        else:

            async def load_card(card: dict[str, Any]) -> list[dict[str, Any]]:
                product = resolve_url(card["url"])
                if product is None:
                    return []
                return [
                    item
                    async for item in _product_flow(
                        product,
                        input_model,
                        provenance={"bestsellerPageData": card["bestsellerPageData"]},
                    )
                ]

            for batch in await gather_bounded(
                [lambda card=card: load_card(card) for card in cards],
                concurrency=_DETAIL_CONCURRENCY,
            ):
                for item in batch:
                    if "error" not in item and emitted >= cap:
                        return
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


async def iter_products(
    input_model: AmazonScrapeInput,
) -> AsyncIterator[dict[str, Any]]:
    """Yield product items for every start URL.

    Each ``categoryOrProductUrls`` entry is classified and dispatched to its
    per-kind flow. A URL that cannot be recognized as an Amazon product /
    search / bestsellers / shortened link yields an ``invalid_url`` error item
    (the failure model is in-stream error items, not exceptions).
    """
    for entry in input_model.categoryOrProductUrls:
        url = entry.get("url") if isinstance(entry, dict) else None
        resolved = resolve_url(url) if url else None
        if resolved is None:
            yield _error(
                "invalid_url",
                "Start URL was malformed or not a recognized Amazon URL.",
                input_url=url,
            )
            continue
        async for item in _FLOWS[resolved.kind](resolved, input_model):
            yield item


async def scrape_products(
    input_model: AmazonScrapeInput, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Collect :func:`iter_products` into a list, honoring an optional ``limit``.

    ``limit`` is a request-time policy guard (used by the route/capability), NOT
    a ceiling in the streaming core.
    """
    from app.capabilities.core.progress import emit_progress

    results: list[dict[str, Any]] = []
    async for item in iter_products(input_model):
        results.append(item)
        emit_progress("scraping", current=len(results), total=limit, unit="product")
        if limit is not None and len(results) >= limit:
            break
    return results
