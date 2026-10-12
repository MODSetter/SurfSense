"""Platform-native Google Maps scraper (Apify Google Maps Scraper-compatible)."""

from .reviews import iter_reviews, scrape_reviews
from .schemas import (
    GoogleMapsReviewsInput,
    GoogleMapsScrapeInput,
    PlaceItem,
    ReviewItem,
)
from .scraper import iter_places, scrape_places

__all__ = [
    "GoogleMapsReviewsInput",
    "GoogleMapsScrapeInput",
    "PlaceItem",
    "ReviewItem",
    "iter_places",
    "iter_reviews",
    "scrape_places",
    "scrape_reviews",
]
