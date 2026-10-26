import re
from urllib.parse import SplitResult

from modules.documents.web_sources.pullers.puller import (
    MAX_REPLIES,
    Fit,
    Listed,
    Listing,
    Pulled,
    Puller,
    Results,
    ToolCall,
)
from modules.documents.web_sources.source_text.plain_text import plain_text
from modules.documents.web_sources.source_text.source_markdown import (
    about,
    bullets,
    price,
    rating,
    review,
    source_markdown,
)

_HOSTS = {"walmart.com", "www.walmart.com"}
# `/ip/<slug>/<id>` or `/ip/<id>`.
_PRODUCT_PATH = re.compile(r"^/ip/(?:[^/]+/)?\d+/?$")


def _fit(url: SplitResult) -> Fit | None:
    if url.hostname not in _HOSTS:
        return None
    return Fit.ONE if _PRODUCT_PATH.match(url.path) else Fit.LIST


def _calls(url: str) -> list[ToolCall]:
    """The page's sample of ten reviews is skipped: the reviews call reads 100."""
    return [
        ToolCall(
            "scrape",
            {
                "urls": [url],
                "max_items": 1,
                "include_details": True,
                "include_reviews_sample": False,
            },
        ),
        ToolCall(
            "reviews",
            {"urls": [url], "max_reviews": MAX_REPLIES, "sort_by": "most-helpful"},
            optional=True,
        ),
    ]


def _written(url: str, results: Results) -> Pulled | None:
    product = next(
        (
            item
            for item in results.get("scrape") or []
            if item.get("name") and not item.get("error")
        ),
        None,
    )
    if product is None:
        return None
    title = product["name"]
    description = "\n\n".join(
        plain_text(part)
        for part in (product.get("shortDescription"), product.get("longDescription"))
        if part
    )
    specifications = product.get("specifications") or {}
    markdown = source_markdown(
        title,
        [
            ("Brand", product.get("brand")),
            ("Price", price(product.get("price"))),
            ("Rating", rating(product.get("stars"), product.get("reviewsCount"))),
            ("Link", product.get("url") or url),
        ],
        [
            ("Description", description),
            ("Specifications", bullets(f"{k}: {v}" for k, v in specifications.items())),
            ("Reviews", bullets(_review(r) for r in results.get("reviews") or [])),
        ],
    )
    return Pulled(title, markdown)


def _review(said: dict) -> str:
    about = [f"{said['rating']:g} stars"] if said.get("rating") is not None else []
    if said.get("submissionTime"):
        about.append(said["submissionTime"])
    return review(said.get("author"), about, said.get("title"), said.get("text"))


def _list_call(url: str, count: int) -> ToolCall:
    """A search's cards only: details are read when a product is added."""
    return ToolCall(
        "scrape",
        {
            "urls": [url],
            "max_items": count,
            "include_details": False,
            "include_reviews_sample": False,
        },
    )


def _list_items(items: list[dict]) -> list[Listed]:
    return [
        Listed(
            product["url"],
            product.get("name") or product["url"],
            about(price(product.get("price")), rating(product.get("stars"), None)),
        )
        for product in items
        if product.get("url") and not product.get("error")
    ]


def _search_call(query: str, count: int) -> ToolCall:
    return ToolCall(
        "scrape",
        {
            "search_terms": [query],
            "max_items": count,
            "include_details": False,
            "include_reviews_sample": False,
        },
    )


PULLER = Puller(
    id="walmart",
    plugin_id="walmart",
    fit=_fit,
    calls=_calls,
    written=_written,
    listing=Listing(_list_call, _list_items),
    search=_search_call,
)
