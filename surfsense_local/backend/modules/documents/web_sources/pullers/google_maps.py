import re
from urllib.parse import SplitResult, parse_qs

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
from modules.documents.web_sources.source_text.source_markdown import (
    about,
    bullets,
    rating,
    source_markdown,
)

_STARS = (
    ("fiveStar", "5 stars"),
    ("fourStar", "4 stars"),
    ("threeStar", "3 stars"),
    ("twoStar", "2 stars"),
    ("oneStar", "1 star"),
)

# google.com, google.co.uk, maps.google.de and the rest.
_GOOGLE_HOST = re.compile(r"^((www|maps)\.)?google\.[a-z.]+$")
# Short links the plugin opens itself, in a browser.
_SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl"}


def _fit(url: SplitResult) -> Fit | None:
    host = url.hostname or ""
    if host in _SHORT_HOSTS:
        return Fit.ONE
    if not _GOOGLE_HOST.match(host):
        return None
    if host.startswith("maps.") and parse_qs(url.query).get("cid"):
        return Fit.ONE
    if not url.path.startswith("/maps"):
        return None
    if url.path.startswith("/maps/place/") or parse_qs(url.query).get("cid"):
        return Fit.ONE
    return Fit.LIST


def _calls(url: str) -> list[ToolCall]:
    """The place's reviews come inside it, so one call reads both."""
    return [
        ToolCall(
            "scrape",
            {
                "urls": [url],
                "max_places": 1,
                "include_details": True,
                "max_reviews": MAX_REPLIES,
            },
        )
    ]


def _written(url: str, results: Results) -> Pulled | None:
    place = next(
        (
            item
            for item in results.get("scrape") or []
            if item.get("title") and not item.get("error")
        ),
        None,
    )
    if place is None:
        return None
    title = place["title"]
    markdown = source_markdown(
        title,
        [
            ("Category", place.get("categoryName")),
            ("Address", place.get("address")),
            ("Phone", place.get("phone")),
            ("Website", place.get("website")),
            ("Rating", rating(place.get("totalScore"), place.get("reviewsCount"))),
            ("Ratings", _spread(place.get("reviewsDistribution") or {})),
            ("Status", _status(place)),
            ("Link", place.get("url") or url),
        ],
        [
            ("About", place.get("description")),
            (
                "Opening hours",
                bullets(_hours(h) for h in place.get("openingHours") or []),
            ),
            ("Reviews", bullets(_review(r) for r in place.get("reviews") or [])),
        ],
    )
    return Pulled(title, markdown)


def _spread(distribution: dict) -> str | None:
    shown = [
        f"{label}: {distribution[key]:,}"
        for key, label in _STARS
        if distribution.get(key) is not None
    ]
    return ", ".join(shown) or None


def _status(place: dict) -> str | None:
    if place.get("permanentlyClosed"):
        return "Permanently closed"
    if place.get("temporarilyClosed"):
        return "Temporarily closed"
    return None


def _hours(hours: dict) -> str:
    return (
        f"{hours['day']}: {hours.get('hours') or ''}".strip()
        if hours.get("day")
        else ""
    )


def _review(review: dict) -> str:
    about = [f"{review['stars']:g} stars"] if review.get("stars") is not None else []
    if review.get("publishedAtDate"):
        about.append(review["publishedAtDate"])
    said = (review.get("text") or "").strip() or "no text"
    reply = (review.get("responseFromOwnerText") or "").strip()
    if reply:
        said += f" Owner's reply: {reply}"
    when = f" ({', '.join(about)})" if about else ""
    return f"**{review.get('name') or 'Someone'}**{when}: {said}"


def _list_call(url: str, count: int) -> ToolCall:
    return ToolCall("scrape", {"urls": [url], "max_places": count})


def _list_items(items: list[dict]) -> list[Listed]:
    return [
        Listed(
            place["url"],
            place.get("title") or place["url"],
            about(place.get("categoryName"), place.get("address")),
        )
        for place in items
        if place.get("url") and not place.get("error")
    ]


def _search_call(query: str, count: int) -> ToolCall:
    return ToolCall("scrape", {"search_queries": [query], "max_places": count})


PULLER = Puller(
    id="google_maps",
    plugin_id="google-maps",
    fit=_fit,
    calls=_calls,
    written=_written,
    listing=Listing(_list_call, _list_items),
    search=_search_call,
)
