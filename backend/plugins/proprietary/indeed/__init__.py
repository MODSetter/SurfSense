"""Platform-native Indeed jobs scraper (anonymous, warmed browser session)."""

from .fetch import IndeedAccessBlockedError
from .schemas import IndeedItem, IndeedScrapeInput
from .scraper import iter_indeed, scrape_indeed

__all__ = [
    "IndeedAccessBlockedError",
    "IndeedItem",
    "IndeedScrapeInput",
    "iter_indeed",
    "scrape_indeed",
]
