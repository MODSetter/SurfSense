"""Platform-native Google Search results scraper (Apify Google Search Results
Scraper-compatible)."""

from .schemas import GoogleSearchScrapeInput, SerpItem
from .scraper import iter_serps, scrape_serps

__all__ = [
    "GoogleSearchScrapeInput",
    "SerpItem",
    "iter_serps",
    "scrape_serps",
]
