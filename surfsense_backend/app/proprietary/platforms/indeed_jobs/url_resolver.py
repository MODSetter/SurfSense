"""Classify Indeed URLs and build search URLs.

Recognizes search pages (``/jobs?q=&l=``), company pages (``/cmp/<slug>/jobs``),
and single jobs (``/viewjob?jk=``); other hosts resolve to ``None``. Also owns
the country->domain map so classification and URL building share one source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse

ResolvedKind = Literal["search", "company", "job"]

# Locale subdomains that deviate from the ISO code; others map to <cc>.indeed.com.
_DOMAIN_OVERRIDES = {"us": "www", "gb": "uk"}

_JT_VALUES = frozenset(
    {
        "fulltime",
        "parttime",
        "contract",
        "internship",
        "temporary",
        "permanent",
        "seasonal",
        "freelance",
    }
)


@dataclass(frozen=True)
class ResolvedUrl:
    kind: ResolvedKind
    value: str  # search query, company slug, or job key
    url: str
    domain: str
    location: str | None = None
    params: dict[str, str] = field(default_factory=dict)


def _is_indeed_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    h = hostname.lower()
    return h == "indeed.com" or h.endswith(".indeed.com")


def country_domain(country: str) -> str:
    """Country code -> Indeed host, e.g. ``us`` -> ``www.indeed.com``."""
    cc = (country or "us").strip().lower()
    return f"{_DOMAIN_OVERRIDES.get(cc, cc)}.indeed.com"


def resolve_url(url: str) -> ResolvedUrl | None:
    """Classify an Indeed URL into a scrape job, or ``None`` if unrecognized."""
    parsed = urlparse(url)
    if not _is_indeed_host(parsed.hostname):
        return None
    domain = parsed.hostname or "www.indeed.com"
    path = (parsed.path or "").rstrip("/")
    query = parse_qs(parsed.query)
    segments = [s for s in path.split("/") if s]

    # /viewjob?jk=<key>
    if path.endswith("/viewjob") or segments[:1] == ["viewjob"]:
        jk = query.get("jk", [None])[0]
        return ResolvedUrl("job", jk, url, domain) if jk else None

    # /cmp/<slug>/jobs
    if segments[:1] == ["cmp"] and "jobs" in segments and len(segments) >= 2:
        return ResolvedUrl("company", segments[1], url, domain)

    # /jobs?q=&l=
    if path.endswith("/jobs") or segments[-1:] == ["jobs"]:
        q = query.get("q", [""])[0]
        loc = query.get("l", [None])[0]
        extra = {
            k: v[0]
            for k, v in query.items()
            if k in ("radius", "sort", "fromage", "jt", "explvl") and v
        }
        return ResolvedUrl("search", q, url, domain, location=loc, params=extra)

    return None


def build_search_url(
    query: str,
    *,
    country: str = "us",
    location: str | None = None,
    radius: int | None = None,
    job_type: str | None = None,
    level: str | None = None,
    remote: str | None = None,
    from_days: int | None = None,
    sort: str = "relevance",
    start: int = 0,
) -> str:
    """Build an Indeed ``/jobs`` search URL.

    Remote/hybrid is passed as a query keyword; Indeed's structured ``sc``
    attribute codes rotate and aren't stable to hardcode.
    """
    domain = country_domain(country)
    q = f"{query} {remote}".strip() if remote else query
    params: dict[str, str] = {"q": q}
    if location:
        params["l"] = location
    if radius is not None:
        params["radius"] = str(radius)
    if job_type in _JT_VALUES:
        params["jt"] = job_type  # type: ignore[assignment]
    if level:
        params["explvl"] = level
    if from_days is not None:
        params["fromage"] = str(from_days)
    if sort == "date":
        params["sort"] = "date"
    if start:
        params["start"] = str(start)
    return f"https://{domain}/jobs?{urlencode(params)}"
