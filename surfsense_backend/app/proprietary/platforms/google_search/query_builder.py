"""Pure query/URL composition for the Google Search scraper.

The ``queries`` input is a newline-separated string mixing plain search terms
and full Google Search URLs (both accepted verbatim by the Apify actor). This
module classifies each entry, folds the advanced-filter fields into search
operators (``site:``, ``intitle:``, ``filetype:``, ``before:``/``after:``, …),
and builds the final search URL — all pure string work, no network, so it is
the part of the skeleton that is implemented and unit-tested up front (like
``url_resolver`` in the Maps scraper).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, quote_plus, urlparse

from .schemas import GoogleSearchScrapeInput

# Google redirected every country ccTLD (google.es, google.co.uk, …) to
# google.com in 2025; localization is controlled by the ``gl`` URL parameter.
# ponytail: we always hit google.com + gl=<countryCode> instead of keeping a
# ~240-entry ccTLD table; the searchQuery.domain output field still reports
# google.com, which is what the redirect would land on anyway.
_GOOGLE_DOMAIN = "google.com"

_RESULTS_PER_PAGE = 10

# Relative date like "8 days", "3 months" (Apify's beforeDate/afterDate).
_RELATIVE_DATE_RE = re.compile(r"^\s*(\d+)\s*(day|week|month|year)s?\s*$", re.I)
_ABSOLUTE_DATE_RE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*$")

# ponytail: calendar-exact month/year arithmetic buys nothing for a search
# date *filter*; 30/365-day approximations are within Google's own precision.
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


@dataclass(frozen=True)
class QueryEntry:
    """One line of the ``queries`` input, classified."""

    kind: str  # "term" | "url"
    value: str  # the search term, or the full Google Search URL


def parse_queries(queries: str) -> list[QueryEntry]:
    """Split the newline-separated ``queries`` input into classified entries."""
    entries: list[QueryEntry] = []
    for raw in queries.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _is_search_url(line):
            entries.append(QueryEntry("url", line))
        else:
            entries.append(QueryEntry("term", line))
    return entries


def _is_search_url(line: str) -> bool:
    if not line.lower().startswith(("http://", "https://")):
        return False
    parsed = urlparse(line)
    host = parsed.hostname or ""
    return "google." in host and parsed.path.startswith("/search")


def term_from_url(url: str) -> str | None:
    """The ``q`` parameter of a Google Search URL (for provenance stamping)."""
    return parse_qs(urlparse(url).query).get("q", [None])[0]


def resolve_date(value: str, *, now: datetime | None = None) -> str | None:
    """Normalize an Apify date input to ``YYYY-MM-DD``.

    Accepts an absolute date (kept as-is) or a relative one like ``"3 months"``
    (resolved from now into the past, in UTC per the Apify spec). Returns
    ``None`` for unparseable input rather than guessing.
    """
    if _ABSOLUTE_DATE_RE.match(value):
        return value.strip()
    match = _RELATIVE_DATE_RE.match(value)
    if not match:
        return None
    count, unit = int(match.group(1)), match.group(2).lower()
    moment = (now or datetime.now(UTC)) - timedelta(days=count * _UNIT_DAYS[unit])
    return moment.strftime("%Y-%m-%d")


def augment_query(term: str, input_model: GoogleSearchScrapeInput) -> str:
    """Fold the advanced-filter fields into the search term as operators.

    Mirrors Apify's documented behavior: ``forceExactMatch`` wraps the whole
    term in quotes; ``site:`` takes precedence over ``related:``; word filters
    use one ``intitle:``/``intext:``/``inurl:`` per word (never the
    ``allin*:`` forms); multiple ``fileTypes`` are OR-joined; ``beforeDate``/
    ``afterDate`` become ``before:``/``after:`` operators.
    """
    parts: list[str] = []
    parts.append(f'"{term}"' if input_model.forceExactMatch else term)

    if input_model.site:
        parts.append(f"site:{input_model.site}")
    elif input_model.relatedToSite:
        parts.append(f"related:{input_model.relatedToSite}")

    for op, words in (
        ("intitle", input_model.wordsInTitle),
        ("intext", input_model.wordsInText),
        ("inurl", input_model.wordsInUrl),
    ):
        for word in words:
            value = f'"{word}"' if " " in word else word
            parts.append(f"{op}:{value}")

    if input_model.fileTypes:
        parts.append(" OR ".join(f"filetype:{ft}" for ft in input_model.fileTypes))

    if input_model.beforeDate:
        resolved = resolve_date(input_model.beforeDate)
        if resolved:
            parts.append(f"before:{resolved}")
    if input_model.afterDate:
        resolved = resolve_date(input_model.afterDate)
        if resolved:
            parts.append(f"after:{resolved}")

    return " ".join(parts)


def build_search_url(
    term: str, input_model: GoogleSearchScrapeInput, *, page: int = 1
) -> str:
    """The full ``google.com/search`` URL for one query page (1-based)."""
    params: list[tuple[str, str]] = [("q", augment_query(term, input_model))]
    if page > 1:
        params.append(("start", str((page - 1) * _RESULTS_PER_PAGE)))
    if input_model.countryCode:
        params.append(("gl", input_model.countryCode.lower()))
    if input_model.searchLanguage:
        params.append(("lr", f"lang_{input_model.searchLanguage}"))
    if input_model.languageCode:
        params.append(("hl", input_model.languageCode))
    if input_model.locationUule:
        params.append(("uule", input_model.locationUule))
    if input_model.quickDateRange:
        params.append(("tbs", f"qdr:{input_model.quickDateRange}"))
    if input_model.includeUnfilteredResults:
        params.append(("filter", "0"))
    query_string = "&".join(f"{k}={quote_plus(v)}" for k, v in params)
    return f"https://www.{_GOOGLE_DOMAIN}/search?{query_string}"


def build_ai_mode_url(term: str, input_model: GoogleSearchScrapeInput) -> str:
    """The Google AI Mode URL (``udm=50``) for one query.

    AI Mode takes the plain conversational query — search operators and
    result-shaping parameters don't apply — plus localization.
    """
    params: list[tuple[str, str]] = [("q", term), ("udm", "50")]
    if input_model.countryCode:
        params.append(("gl", input_model.countryCode.lower()))
    if input_model.languageCode:
        params.append(("hl", input_model.languageCode))
    query_string = "&".join(f"{k}={quote_plus(v)}" for k, v in params)
    return f"https://www.{_GOOGLE_DOMAIN}/search?{query_string}"
