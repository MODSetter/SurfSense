import re
from urllib.parse import SplitResult, parse_qs

from modules.documents.web_sources.pullers.puller import (
    Fit,
    Listed,
    Listing,
    Pulled,
    Puller,
    Results,
    ToolCall,
)
from modules.documents.web_sources.source_text.source_markdown import (
    about,
    bullets,
    price,
    rating,
    review,
    source_markdown,
)

# amazon.com, amazon.co.uk, amazon.de and every other marketplace.
_AMAZON_HOST = re.compile(r"^(www\.|smile\.)?amazon\.[a-z.]+$")
# Short links the plugin follows itself.
_SHORT_HOSTS = {"a.co", "amzn.to", "amzn.eu"}
_PRODUCT_PATH = re.compile(r"/(dp|gp/product|gp/aw/d)/[A-Z0-9]{10}", re.IGNORECASE)


def _fit(url: SplitResult) -> Fit | None:
    if url.hostname in _SHORT_HOSTS:
        return Fit.ONE
    if not _AMAZON_HOST.match(url.hostname or ""):
        return None
    if _PRODUCT_PATH.search(url.path) or parse_qs(url.query).get("asin"):
        return Fit.ONE
    return Fit.LIST


def _calls(url: str) -> list[ToolCall]:
    """Its reviews are the product page's: the plugin takes no count of them."""
    return [
        ToolCall("scrape", {"urls": [url], "max_items": 1, "include_details": True})
    ]


def _written(url: str, results: Results) -> Pulled | None:
    product = next(
        (
            item
            for item in results.get("scrape") or []
            if item.get("title") and not item.get("error")
        ),
        None,
    )
    if product is None:
        return None
    title = product["title"]
    summary = (product.get("aiReviewsSummary") or {}).get("text")
    markdown = source_markdown(
        title,
        [
            ("Brand", product.get("brand")),
            ("Author", product.get("author")),
            ("Price", price(product.get("price"))),
            ("Rating", rating(product.get("stars"), product.get("reviewsCount"))),
            ("Link", product.get("url") or url),
        ],
        [
            ("About this item", bullets(product.get("features") or [])),
            (
                "Description",
                product.get("description") or product.get("bookDescription"),
            ),
            (
                "Details",
                bullets(_detail(d) for d in product.get("productOverview") or []),
            ),
            ("What customers say", summary),
            (
                "Reviews",
                bullets(_review(r) for r in product.get("productPageReviews") or []),
            ),
        ],
    )
    return Pulled(title, markdown)


def _detail(detail: dict) -> str:
    return (
        f"{detail['name']}: {detail.get('value') or ''}".strip()
        if detail.get("name")
        else ""
    )


def _review(said: dict) -> str:
    about = [f"{said['stars']:g} stars"] if said.get("stars") is not None else []
    if said.get("date"):
        about.append(said["date"])
    if said.get("verified"):
        about.append("verified purchase")
    return review(said.get("author"), about, said.get("title"), said.get("text"))


def _list_call(url: str, count: int) -> ToolCall:
    """A search's cards only: details are read when a product is added."""
    return ToolCall(
        "scrape", {"urls": [url], "max_items": count, "include_details": False}
    )


def _list_items(items: list[dict]) -> list[Listed]:
    return [
        Listed(
            product["url"],
            product.get("title") or product["url"],
            about(price(product.get("price")), rating(product.get("stars"), None)),
        )
        for product in items
        if product.get("url") and not product.get("error")
    ]


def _search_call(query: str, count: int) -> ToolCall:
    return ToolCall(
        "scrape",
        {"search_terms": [query], "max_items": count, "include_details": False},
    )


PULLER = Puller(
    id="amazon",
    plugin_id="amazon",
    fit=_fit,
    calls=_calls,
    written=_written,
    listing=Listing(_list_call, _list_items),
    search=_search_call,
)
