"""Offline checks for the Google Maps scraper skeleton.

Covers the pure parts: URL classification and Apify-spec schema defaults/
serialization. The live flows (place / reviews / search) are covered by the
e2e scripts and the fixture-based parser tests.
"""

import pytest

from app.proprietary.scrapers.google_maps import (
    GoogleMapsReviewsInput,
    GoogleMapsScrapeInput,
    PlaceItem,
    ReviewItem,
)
from app.proprietary.scrapers.google_maps.url_resolver import extract_fid, resolve_url


@pytest.mark.parametrize(
    ("url", "kind", "value"),
    [
        (
            "https://www.google.com/maps/place/Kim's+Island/@40.51,-74.24,17z/data=!4m6",
            "place",
            "Kim's Island",
        ),
        (
            "https://www.google.com/maps/search/restaurants/@52.5190603,13.388574,13z/",
            "search",
            "restaurants",
        ),
        ("https://www.google.com/maps/reviews/data=!4m8!14m7", "reviews", None),
        (
            "https://www.google.com/maps?cid=7838756667406262025",
            "cid",
            "7838756667406262025",
        ),
        ("https://goo.gl/maps/abc123", "shortlink", None),
        ("https://maps.app.goo.gl/xyz", "shortlink", None),
    ],
)
def test_resolve_url(url, kind, value):
    resolved = resolve_url(url)
    assert resolved is not None
    assert resolved.kind == kind
    if value is not None:
        assert resolved.value == value


def test_resolve_url_rejects_non_maps():
    assert resolve_url("https://example.com/maps/place/foo") is None
    assert resolve_url("https://www.google.com/search?q=pizza") is None


def test_extract_fid():
    url = (
        "https://www.google.com/maps/place/Kim's+Island/@40.51,-74.24,17z/"
        "data=!4m6!3m5!1s0x89c3ca9c11f90c25:0x6cc8dba851799f09!8m2"
    )
    assert extract_fid(url) == "0x89c3ca9c11f90c25:0x6cc8dba851799f09"
    assert extract_fid("https://www.google.com/maps/place/Foo") is None
    assert resolve_url(url).fid == "0x89c3ca9c11f90c25:0x6cc8dba851799f09"


def test_scrape_input_defaults_match_apify_spec():
    inp = GoogleMapsScrapeInput()
    assert inp.language == "en"
    assert inp.maxCrawledPlacesPerSearch is None  # empty = all places
    assert inp.searchMatching == "all"
    assert inp.website == "allPlaces"
    assert inp.reviewsSort == "newest"
    assert inp.reviewsOrigin == "all"
    assert inp.scrapeReviewsPersonalData is True
    assert inp.maxCompetitorsToAnalyze == 30
    assert inp.scrapeSocialMediaProfiles.facebooks is False
    # Unknown fields are accepted (extra="allow") so parity is additive.
    GoogleMapsScrapeInput(someFutureField=1)


def test_reviews_input_defaults_match_apify_spec():
    inp = GoogleMapsReviewsInput()
    assert inp.maxReviews == 10_000_000
    assert inp.reviewsSort == "newest"
    assert inp.personalData is True


def test_output_items_serialize_full_shape():
    place = PlaceItem(title="Kim's Island", placeId="ChIJx").to_output()
    assert place["title"] == "Kim's Island"
    assert place["permanentlyClosed"] is False
    assert place["categories"] == []
    assert "reviewsDistribution" in place  # unsourced fields still emitted

    review = ReviewItem(reviewId="abc", stars=5).to_output()
    assert review["stars"] == 5
    assert review["reviewImageUrls"] == []
    assert "responseFromOwnerText" in review
