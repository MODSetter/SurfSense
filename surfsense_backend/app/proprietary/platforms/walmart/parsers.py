"""Pure parsers for Walmart's hidden ``__NEXT_DATA__`` JSON.

Product, listing, and review data all live in the same Next.js state tree; these
functions navigate it defensively (via :func:`.next_data.dig`) and normalize the
fields into the stable output shape. Missing sections yield ``None``/``[]`` so an
isolated schema change never discards an otherwise usable record.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from .next_data import dig, initial_data

_WALMART_ORIGIN = "https://www.walmart.com"


# --------------------------------------------------------------------------- #
# Shared helpers.                                                             #
# --------------------------------------------------------------------------- #


def _price(node: Any) -> dict[str, Any] | None:
    """Normalize a Walmart price node into ``{value, currency}``."""
    if not isinstance(node, dict):
        return None
    value = node.get("price")
    currency = node.get("currencyUnit")
    if value is None and currency is None:
        return None
    return {"value": value, "currency": currency}


def _seller(raw: dict[str, Any]) -> dict[str, Any] | None:
    name = raw.get("sellerName") or raw.get("sellerDisplayName")
    seller_id = raw.get("sellerId")
    if not name and not seller_id:
        return None
    is_walmart = bool(name) and "walmart" in name.lower()
    return {
        "id": seller_id,
        "name": name,
        "type": "WALMART" if is_walmart else "MARKETPLACE",
    }


def _absolute(url: str | None) -> str | None:
    return urljoin(_WALMART_ORIGIN, url) if url else None


# --------------------------------------------------------------------------- #
# Listing / search cards.                                                     #
# --------------------------------------------------------------------------- #


def _listing_card(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one search/category result item into a product card."""
    item_id = raw.get("usItemId") or raw.get("id")
    name = raw.get("name")
    if not item_id or not name:
        return None
    price_info = raw.get("priceInfo") or {}
    availability = raw.get("availabilityStatusV2") or {}
    image = raw.get("imageInfo") or {}
    return {
        "usItemId": str(item_id),
        "name": name,
        "brand": raw.get("brand"),
        "url": _absolute(raw.get("canonicalUrl")),
        "price": _price(price_info.get("currentPrice"))
        or ({"value": raw.get("price")} if raw.get("price") is not None else None),
        "listPrice": _price(price_info.get("wasPrice")),
        "stars": raw.get("averageRating"),
        "reviewsCount": raw.get("numberOfReviews"),
        "seller": _seller(raw),
        "availabilityStatus": availability.get("value")
        or ("OUT_OF_STOCK" if raw.get("isOutOfStock") else None),
        "inStock": (availability.get("value") == "IN_STOCK")
        if availability.get("value")
        else (raw.get("isOutOfStock") is False if "isOutOfStock" in raw else None),
        "thumbnailImage": image.get("thumbnailUrl") or raw.get("image"),
        "sponsored": raw.get("isSponsoredFlag"),
    }


def parse_listing_page(next_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract normalized product cards from a search/category/browse page."""
    data = initial_data(next_data)
    if data is None:
        return []
    stacks = dig(data, "searchResult", "itemStacks")
    if not isinstance(stacks, list):
        return []
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for stack in stacks:
        for raw in (stack or {}).get("items") or []:
            if not isinstance(raw, dict) or raw.get("__typename") not in (
                None,
                "Product",
            ):
                continue
            card = _listing_card(raw)
            if card and card["usItemId"] not in seen:
                seen.add(card["usItemId"])
                cards.append(card)
    return cards


# --------------------------------------------------------------------------- #
# Product detail.                                                             #
# --------------------------------------------------------------------------- #


def _images(image_info: dict[str, Any]) -> list[str]:
    images: list[str] = []
    for entry in image_info.get("allImages") or []:
        url = entry.get("url") if isinstance(entry, dict) else None
        if url and url not in images:
            images.append(url)
    return images


def _breadcrumbs(product: dict[str, Any]) -> list[str]:
    """Category breadcrumb names, root→leaf.

    Walmart ships ``category.path`` as a list of ``{name, url}`` nodes, e.g.
    ``[{"name": "Home Improvement"}, ..., {"name": "Air Conditioners"}]`` — not
    a string.
    """
    path = dig(product, "category", "path")
    if not isinstance(path, list):
        return []
    return [node["name"] for node in path if isinstance(node, dict) and node.get("name")]


def _reviews_sample(
    reviews: dict[str, Any] | None, limit: int = 10
) -> dict[str, Any] | None:
    if not isinstance(reviews, dict):
        return None
    customer = reviews.get("customerReviews") or []
    return {
        "averageOverallRating": reviews.get("averageOverallRating"),
        "totalReviewCount": reviews.get("totalReviewCount"),
        "aspects": reviews.get("aspects") or [],
        "topReviews": [
            normalize_review(r) for r in customer[:limit] if isinstance(r, dict)
        ],
    }


def parse_product(
    next_data: dict[str, Any], *, url: str, include_reviews_sample: bool = True
) -> dict[str, Any]:
    """Extract normalized product fields from a product detail page."""
    data = initial_data(next_data)
    product = dig(data, "data", "product") if data else None
    if not isinstance(product, dict):
        return {}
    idml = dig(data, "data", "idml") if data else None
    reviews = dig(data, "data", "reviews") if data else None
    price_info = product.get("priceInfo") or {}
    image_info = product.get("imageInfo") or {}
    availability = product.get("availabilityStatus")
    breadcrumbs = _breadcrumbs(product)

    fields: dict[str, Any] = {
        "usItemId": str(product.get("usItemId") or product.get("id") or "") or None,
        "name": product.get("name"),
        "brand": product.get("brand"),
        "url": url,
        "price": _price(price_info.get("currentPrice")),
        "listPrice": _price(price_info.get("wasPrice")),
        "currency": dig(price_info, "currentPrice", "currencyUnit"),
        "availabilityStatus": availability,
        "inStock": availability == "IN_STOCK" if availability else None,
        "stars": product.get("averageRating"),
        "reviewsCount": product.get("numberOfReviews"),
        "seller": _seller(product),
        "manufacturerName": product.get("manufacturerName"),
        "shortDescription": product.get("shortDescription"),
        "longDescription": (idml or {}).get("longDescription")
        if isinstance(idml, dict)
        else None,
        "thumbnailImage": image_info.get("thumbnailUrl"),
        "images": _images(image_info),
        "category": breadcrumbs[-1] if breadcrumbs else None,
        "breadCrumbs": breadcrumbs,
        "variants": product.get("variantCriteria") or [],
    }
    if include_reviews_sample:
        fields["reviewsSample"] = _reviews_sample(reviews)
    return {key: value for key, value in fields.items() if value is not None}


# --------------------------------------------------------------------------- #
# Reviews (deep pagination).                                                  #
# --------------------------------------------------------------------------- #


def normalize_review(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Walmart ``customerReviews`` record into a ``ReviewItem`` dict."""
    badges = raw.get("badges") or []
    verified = any(
        isinstance(b, dict) and b.get("id") == "VerifiedPurchaser" for b in badges
    )
    photos = raw.get("photos") or raw.get("media") or []
    images: list[str] = []
    for photo in photos:
        if not isinstance(photo, dict):
            continue
        url = photo.get("normalUrl") or dig(photo, "sizes", "normal", "url")
        if url and url not in images:
            images.append(url)
    responses = raw.get("clientResponses") or []
    seller_response = None
    if responses and isinstance(responses[0], dict):
        seller_response = responses[0].get("response") or responses[0].get(
            "responseText"
        )
    return {
        "reviewId": raw.get("reviewId"),
        "rating": raw.get("rating"),
        "title": raw.get("reviewTitle"),
        "text": raw.get("reviewText"),
        "submissionTime": raw.get("reviewSubmissionTime"),
        "author": raw.get("userNickname"),
        "verifiedPurchase": verified,
        "positiveFeedback": raw.get("positiveFeedback"),
        "negativeFeedback": raw.get("negativeFeedback"),
        "images": images,
        "syndicated": bool(raw.get("syndicationSource")),
        "sellerResponse": seller_response,
    }


def parse_reviews_page(next_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract normalized reviews from one ``/reviews/product/{id}`` page."""
    data = initial_data(next_data)
    reviews = dig(data, "data", "reviews") if data else None
    customer = reviews.get("customerReviews") if isinstance(reviews, dict) else None
    if not isinstance(customer, list):
        return []
    return [normalize_review(r) for r in customer if isinstance(r, dict)]
