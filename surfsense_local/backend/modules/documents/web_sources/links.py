"""Which puller takes a link: the site's own when there is one, Web Crawl otherwise."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from modules.documents.web_sources.pullers import (
    amazon,
    google_maps,
    indeed,
    instagram,
    reddit,
    tiktok,
    walmart,
    web_page,
    youtube,
)
from modules.documents.web_sources.pullers.puller import Fit, Puller

PULLERS = (
    youtube.PULLER,
    tiktok.PULLER,
    google_maps.PULLER,
    amazon.PULLER,
    walmart.PULLER,
    indeed.PULLER,
    reddit.PULLER,
    instagram.PULLER,
)


@dataclass(frozen=True)
class Route:
    puller: Puller
    fit: Fit


def routed(url: str) -> Route:
    parts = urlsplit(url)
    for puller in PULLERS:
        fit = puller.fit(parts)
        if fit is not None:
            return Route(puller, fit)
    return Route(web_page.PULLER, Fit.ONE)


def puller_named(puller_id: str) -> Puller:
    return next(p for p in (*PULLERS, web_page.PULLER) if p.id == puller_id)
