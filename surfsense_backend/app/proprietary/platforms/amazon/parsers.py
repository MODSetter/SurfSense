"""Pure parsers for public Amazon HTML.

Selectors cover stable element IDs first and use small, explicit fallbacks for
layout variants. Missing sections return empty or nullable values so isolated
markup changes do not discard an otherwise usable product.
"""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from scrapling.parser import Adaptor

_NUMBER_RE = re.compile(r"[\d,.]+")
_ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
_ASIN_IN_TEXT_RE = re.compile(r"\b[A-Z0-9]{10}\b")
_CURRENCY_BY_SYMBOL = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}
_JSON_ASSIGNMENT_RE = re.compile(
    r"(?:dimensionValuesDisplayData|variationValues|dimensionToAsinMap)"
    r"""\s*["']?\s*:\s*(\{.*?\})(?:,\s*["']|\s*;)""",
    re.DOTALL,
)


def _one(node: Any, selector: str) -> Any | None:
    found = node.css(selector)
    return found[0] if found else None


def _text(node: Any | None) -> str | None:
    if node is None:
        return None
    raw = node.get_all_text(strip=True)
    return re.sub(r"\s+", " ", raw).strip() or None


def _texts(node: Any, selector: str) -> list[str]:
    values: list[str] = []
    for match in node.css(selector):
        value = _text(match)
        if value and value not in values:
            values.append(value)
    return values


def _first_text(node: Any, *selectors: str) -> str | None:
    for selector in selectors:
        value = _text(_one(node, selector))
        if value:
            return value
    return None


def _attr(node: Any | None, name: str) -> str | None:
    if node is None:
        return None
    value = node.attrib.get(name)
    return str(value).strip() if value else None


def _first_attr(node: Any, name: str, *selectors: str) -> str | None:
    for selector in selectors:
        value = _attr(_one(node, selector), name)
        if value:
            return value
    return None


def _integer(value: str | None) -> int | None:
    if not value:
        return None
    match = _NUMBER_RE.search(value)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    return int(digits) if digits else None


def _float(value: str | None) -> float | None:
    if not value:
        return None
    match = _NUMBER_RE.search(value)
    if not match:
        return None
    token = match.group(0)
    if "," in token and "." in token:
        decimal = "," if token.rfind(",") > token.rfind(".") else "."
        grouping = "." if decimal == "," else ","
        token = token.replace(grouping, "").replace(decimal, ".")
    elif (
        token.count(",") == 1
        and "." not in token
        and len(token.rsplit(",", 1)[1]) <= 2
    ):
        token = token.replace(",", ".")
    else:
        token = token.replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def _price(value: str | None) -> dict[str, Any] | None:
    amount = _float(value)
    if amount is None:
        return None
    currency = next(
        (
            code
            for symbol, code in _CURRENCY_BY_SYMBOL.items()
            if symbol in (value or "")
        ),
        None,
    )
    if currency is None and value:
        match = re.search(r"\b(USD|EUR|GBP|JPY|INR|CAD|AUD)\b", value)
        currency = match.group(1) if match else None
    return {"value": amount, "currency": currency}


def _absolute(domain: str, href: str | None) -> str | None:
    return urljoin(f"https://{domain}", href) if href else None


def _asin_from_href(href: str | None) -> str | None:
    if not href:
        return None
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", href)
    return match.group(1) if match else None


def _embedded_json(html: str, key: str) -> Any | None:
    """Decode a JSON value assigned to ``key`` inside an inline script."""
    marker = re.search(rf"""["']?{re.escape(key)}["']?\s*:\s*""", html)
    if marker is None:
        return None
    start = marker.end()
    while start < len(html) and html[start].isspace():
        start += 1
    if start >= len(html) or html[start] not in "[{":
        return None
    opening = html[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(html)):
        char = html[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : index + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _stars_breakdown(doc: Adaptor) -> dict[str, float | None] | None:
    breakdown: dict[str, float | None] = {}
    for row in doc.css("#histogramTable tr, [data-hook='rating-histogram'] tr"):
        label = _first_text(row, ".a-text-left", "td:first-child", "span")
        percent = _first_text(row, ".a-text-right", "td:last-child")
        star = _integer(label)
        value = _float(percent)
        if star and 1 <= star <= 5 and value is not None:
            breakdown[f"{star}star"] = value / 100 if value > 1 else value
    return breakdown or None


def _variant_data(
    html: str,
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    display = _embedded_json(html, "dimensionValuesDisplayData")
    variants = _embedded_json(html, "variationValues")
    asins: list[str] = []
    details: list[dict[str, Any]] = []
    attributes: list[dict[str, Any]] = []

    if isinstance(display, dict):
        for asin, values in display.items():
            if _ASIN_RE.match(str(asin)):
                asins.append(str(asin))
                details.append({"asin": str(asin), "values": values})
    if isinstance(variants, dict):
        for name, values in variants.items():
            attributes.append({"name": name, "values": values})
        for value in variants.values():
            if isinstance(value, list):
                for candidate in value:
                    if isinstance(candidate, str) and _ASIN_RE.match(candidate):
                        asins.append(candidate)
    return list(dict.fromkeys(asins)), details, attributes


def _attributes(doc: Adaptor) -> tuple[list[dict[str, str]], dict[str, str]]:
    pairs: list[dict[str, str]] = []
    mapped: dict[str, str] = {}
    for row in doc.css(
        "#productDetails_techSpec_section_1 tr, "
        "#productDetails_detailBullets_sections1 tr, "
        "#detailBullets_feature_div li"
    ):
        name = _first_text(row, "th", ".a-text-bold")
        value = _first_text(row, "td", "span:not(.a-text-bold)")
        if name and value:
            name = name.rstrip(": \u200e")
            pairs.append({"name": name, "value": value})
            mapped[name] = value
    return pairs, mapped


def _reviews(
    doc: Adaptor, domain: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    local: list[dict[str, Any]] = []
    foreign: list[dict[str, Any]] = []
    for node in doc.css("[data-hook='review']"):
        review = {
            "id": _attr(node, "id"),
            "title": _first_text(node, "[data-hook='review-title']"),
            "stars": _float(_first_text(node, "[data-hook='review-star-rating']")),
            "text": _first_text(node, "[data-hook='review-body']"),
            "author": _first_text(node, ".a-profile-name"),
            "date": _first_text(node, "[data-hook='review-date']"),
            "verified": _one(node, "[data-hook='avp-badge']") is not None,
            "helpfulVotes": _integer(
                _first_text(node, "[data-hook='helpful-vote-statement']")
            ),
        }
        if any(value is not None for value in review.values()):
            target = (
                foreign
                if "other countries" in (_text(node) or "").lower()
                or "cm_cr_arp_d_rvw_rvwer" in (_attr(node, "class") or "")
                else local
            )
            target.append(review)
    return local, foreign


def parse_product(
    html: str, *, asin: str, url: str, domain: str | None = None
) -> dict[str, Any]:
    """Parse one product detail page into output-model fields."""
    doc = Adaptor(html)
    domain = domain or (urlparse(url).hostname or "www.amazon.com")
    title = _first_text(doc, "#productTitle", "#title")
    price_text = _first_text(
        doc,
        "#corePrice_feature_div .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        "#apex_desktop .a-price .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        ".priceToPay .a-offscreen",
        "#price_inside_buybox",
        "#centerCol .a-price .a-offscreen",
    )
    list_price_text = _first_text(
        doc,
        "#corePrice_feature_div .basisPrice .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .basisPrice .a-offscreen",
        ".priceBlockStrikePriceString",
        "#centerCol .a-price.a-text-price .a-offscreen",
    )
    availability = _first_text(doc, "#availability", "#outOfStock")
    availability_lower = (availability or "").lower()
    in_stock = (
        None
        if availability is None
        else not any(
            word in availability_lower for word in ("unavailable", "out of stock")
        )
    )
    brand_link = _one(doc, "#bylineInfo")
    brand_text = _text(brand_link)
    brand = (
        re.sub(r"^(visit the |brand:\s*)| store$", "", brand_text, flags=re.IGNORECASE)
        if brand_text
        else None
    )
    variant_asins, variant_details, variant_attributes = _variant_data(html)
    attrs, attrs_mapped = _attributes(doc)
    local_reviews, foreign_reviews = _reviews(doc, domain)

    high_res: list[str] = []
    gallery: list[str] = []
    for image in doc.css("#altImages img, #landingImage, #imgTagWrapperId img"):
        thumb = _attr(image, "src")
        if thumb and thumb not in gallery:
            gallery.append(thumb)
        dynamic = _attr(image, "data-a-dynamic-image")
        if dynamic:
            try:
                decoded = json.loads(unescape(dynamic))
                for candidate in decoded:
                    if candidate not in high_res:
                        high_res.append(candidate)
            except (json.JSONDecodeError, TypeError):
                pass
        zoom = _attr(image, "data-old-hires")
        if zoom and zoom not in high_res:
            high_res.append(zoom)

    ranks: list[dict[str, Any]] = []
    for node in doc.css(
        "#detailBulletsWrapper_feature_div li, #productDetails_detailBullets_sections1 tr"
    ):
        text = _text(node)
        if not text or "best sellers rank" not in text.lower():
            continue
        for rank, category in re.findall(r"#([\d,]+)\s+in\s+([^#(]+)", text):
            ranks.append(
                {"rank": int(rank.replace(",", "")), "category": category.strip()}
            )

    aplus = _one(doc, "#aplus, #aplus_feature_div")
    brand_story = _one(doc, "#brandStory_feature_div, .apm-brand-story")
    store_href = _attr(brand_link, "href")
    reviews_link = _first_attr(
        doc, "href", "#acrCustomerReviewLink", "[data-hook='see-all-reviews-link-foot']"
    )
    seller_link = _one(
        doc,
        "#sellerProfileTriggerId, #merchant-info a[href*='seller='], a[href*='/sp?seller=']",
    )
    seller_href = _attr(seller_link, "href")
    seller_id = (parse_qs(urlparse(seller_href or "").query).get("seller") or [None])[0]
    # Fall back to the buy-box "Sold by" name when there is no seller profile link
    # (Amazon-direct items and some link-less third-party merchants).
    seller_name = _text(seller_link) or _first_text(
        doc,
        "#tabular-buybox [tabular-attribute-name='Sold by'] .tabular-buybox-text",
        "#merchantInfoFeature_feature_div .offer-display-feature-text-message",
    )
    return {
        "title": title,
        "url": url,
        "asin": asin,
        "originalAsin": asin,
        "brand": brand,
        "author": _first_text(
            doc, ".author", "#bylineInfo_feature_div .contributorNameID"
        ),
        "price": _price(price_text),
        "listPrice": _price(list_price_text),
        "shippingPrice": _price(
            _first_text(doc, "#deliveryBlockMessage .a-color-secondary")
        ),
        "inStock": in_stock,
        "inStockText": availability,
        "delivery": _first_text(
            doc, "#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE"
        ),
        "fastestDelivery": _first_text(
            doc, "#mir-layout-DELIVERY_BLOCK-slot-SECONDARY_DELIVERY_MESSAGE_LARGE"
        ),
        "condition": _first_text(
            doc, "#buyNew_noncbb .a-color-price", "#usedAccordionRow"
        ),
        "stars": _float(
            _first_text(doc, "#acrPopover", "[data-hook='rating-out-of-text']")
        ),
        "starsBreakdown": _stars_breakdown(doc),
        "reviewsCount": _integer(_first_text(doc, "#acrCustomerReviewText")),
        "answeredQuestions": _integer(_first_text(doc, "#askATFLink")),
        "aiReviewsSummary": (
            {
                "text": _first_text(
                    doc, "#product-summary, [data-hook='cr-insights-widget']"
                )
            }
            if _first_text(doc, "#product-summary, [data-hook='cr-insights-widget']")
            else None
        ),
        "monthlyPurchaseVolume": _first_text(
            doc, "#social-proofing-faceout-title-tk_bought"
        ),
        "breadCrumbs": " > ".join(
            _texts(doc, "#wayfinding-breadcrumbs_feature_div li a")
        )
        or None,
        "description": _first_text(
            doc, "#productDescription", "#bookDescription_feature_div"
        ),
        "features": _texts(doc, "#feature-bullets li span.a-list-item"),
        "sustainabilityFeatures": [
            {"text": value}
            for value in _texts(doc, "#sustainability_feature_div .a-list-item")
        ],
        "videosCount": _integer(_first_text(doc, "#videoCount")),
        "visitStoreLink": (
            {"text": brand_text, "url": _absolute(domain, store_href)}
            if store_href
            else None
        ),
        "thumbnailImage": _first_attr(doc, "src", "#landingImage", "#imgBlkFront"),
        "galleryThumbnails": gallery,
        "highResolutionImages": high_res,
        "aPlusContent": (
            {
                "text": _text(aplus),
                "images": [
                    _attr(img, "src") for img in aplus.css("img") if _attr(img, "src")
                ],
            }
            if aplus is not None
            else None
        ),
        "brandStory": {"text": _text(brand_story)} if brand_story is not None else None,
        "returnPolicy": _first_text(
            doc, "#returnsInfoFeature_feature_div", "#RETURNS_POLICY"
        ),
        "support": _first_text(doc, "#support_feature_div"),
        "variantAsins": variant_asins,
        "variantDetails": variant_details,
        "variantAttributes": variant_attributes,
        "attributes": attrs,
        "attributesMapped": attrs_mapped or None,
        "productOverview": [
            {
                "name": _first_text(row, "td:first-child"),
                "value": _first_text(row, "td:last-child"),
            }
            for row in doc.css("#productOverview_feature_div tr")
            if _first_text(row, "td:first-child")
        ],
        "seller": (
            {
                "id": seller_id,
                "name": seller_name,
                "url": _absolute(domain, seller_href),
            }
            if (seller_link is not None or seller_name)
            else None
        ),
        "bestsellerRanks": ranks,
        "isAmazonChoice": _one(doc, "#acBadge_feature_div, .ac-badge-wrapper")
        is not None,
        "amazonChoiceText": _first_text(doc, "#acBadge_feature_div, .ac-badge-wrapper"),
        "reviewsLink": _absolute(domain, reviews_link),
        "hasReviews": bool(local_reviews or foreign_reviews),
        "productPageReviews": local_reviews,
        "productPageReviewsFromOtherCountries": foreign_reviews,
    }


def parse_search_page(
    html: str, *, page: int = 1, domain: str = "www.amazon.com"
) -> list[dict[str, Any]]:
    """Parse product cards from a search or category page."""
    doc = Adaptor(html)
    cards: list[dict[str, Any]] = []
    for position, node in enumerate(
        doc.css(
            "[data-component-type='s-search-result'][data-asin], [data-asin].s-result-item"
        ),
        start=1,
    ):
        asin = (_attr(node, "data-asin") or "").upper()
        if not _ASIN_RE.match(asin):
            continue
        href = _first_attr(node, "href", "h2 a", "a.a-link-normal")
        title = _first_text(node, "h2", "h2 span", ".a-size-base-plus")
        cards.append(
            {
                "asin": asin,
                "originalAsin": asin,
                "title": title,
                "url": _absolute(domain, href) or f"https://{domain}/dp/{asin}",
                "price": _price(_first_text(node, ".a-price .a-offscreen")),
                "stars": _float(_first_text(node, ".a-icon-alt")),
                "reviewsCount": _integer(
                    _first_text(node, "[aria-label$='ratings']", ".s-underline-text")
                ),
                "thumbnailImage": _first_attr(node, "src", ".s-image"),
                "categoryPageData": {
                    "position": position,
                    "page": page,
                    "isSponsored": "sponsored" in (_text(node) or "").lower(),
                    "isBestSeller": _one(node, ".a-badge-text, .s-badge-text")
                    is not None,
                },
            }
        )
    return cards


def parse_aod_offers(
    html: str, *, domain: str = "www.amazon.com"
) -> list[dict[str, Any]]:
    """Parse rows from the public all-offers panel."""
    doc = Adaptor(html)
    offers: list[dict[str, Any]] = []
    for position, node in enumerate(
        doc.css("#aod-offer, .aod-information-block"), start=1
    ):
        seller_link = _one(
            node, "#aod-offer-soldBy a[href*='seller='], a[href*='/sp?']"
        )
        href = _attr(seller_link, "href")
        query = parse_qs(urlparse(href or "").query)
        seller_id = (query.get("seller") or [None])[0]
        offers.append(
            {
                "position": position,
                "price": _price(_first_text(node, ".a-price .a-offscreen")),
                "condition": _first_text(
                    node, "#aod-offer-heading", ".aod-information-block"
                ),
                "delivery": _first_text(node, "#mir-layout-DELIVERY_BLOCK"),
                "seller": {
                    "id": seller_id,
                    "name": _text(seller_link)
                    or _first_text(node, "#aod-offer-soldBy .a-color-base"),
                    "url": _absolute(domain, href),
                },
                "isPinnedOffer": _one(node, "#aod-pinned-offer, .aod-pinned-offer")
                is not None,
            }
        )
    return offers


def parse_seller(
    html: str, *, seller_id: str | None = None, domain: str = "www.amazon.com"
) -> dict[str, Any]:
    """Parse the public summary of a seller profile."""
    doc = Adaptor(html)
    return {
        "id": seller_id,
        "name": _first_text(doc, "#sellerName", "#seller-profile-container h1", "h1"),
        "url": f"https://{domain}/sp?seller={seller_id}" if seller_id else None,
        "reviewsCount": _integer(
            _first_text(doc, "#seller-feedback-summary", "#feedback-summary-table")
        ),
        "averageRating": _float(
            _first_text(doc, "#feedback-summary-table .a-icon-alt", ".a-icon-star")
        ),
    }


def parse_bestsellers_page(
    html: str, *, page: int = 1, domain: str = "www.amazon.com"
) -> list[dict[str, Any]]:
    """Parse ranked products from a best-sellers page."""
    doc = Adaptor(html)
    items: list[dict[str, Any]] = []
    nodes = doc.css("#gridItemRoot, .zg-grid-general-faceout, [id^='p13n-asin-index-']")
    for fallback_rank, node in enumerate(nodes, start=1):
        href = _first_attr(node, "href", "a[href*='/dp/']", "a[href*='/gp/product/']")
        asin = _asin_from_href(href) or (_attr(node, "data-asin") or None)
        if not asin or not _ASIN_RE.match(asin):
            continue
        rank = _integer(_first_text(node, ".zg-bdg-text")) or fallback_rank
        items.append(
            {
                "asin": asin,
                "originalAsin": asin,
                "title": _first_text(
                    node, "._cDEzb_p13n-sc-css-line-clamp-3_g3dy1", "img"
                ),
                "url": _absolute(domain, href) or f"https://{domain}/dp/{asin}",
                "price": _price(_first_text(node, ".a-price .a-offscreen")),
                "stars": _float(_first_text(node, ".a-icon-alt")),
                "thumbnailImage": _first_attr(node, "src", "img"),
                "bestsellerPageData": {"rank": rank, "page": page},
            }
        )
    return items
