from urllib.parse import urlsplit

import pytest

from modules.documents.web_sources.pullers.google_maps import PULLER
from modules.documents.web_sources.pullers.puller import Fit, Listed, Pulled, ToolCall

pytestmark = pytest.mark.unit

PLACE = "https://www.google.com/maps/place/Harbour+Tide+Cafe/@50.1,-5.0,17z"


def place(**changed: object) -> dict:
    """A place as the Google Maps plugin's `scrape` answers it, with details and reviews."""
    return {
        "title": "Harbour Tide Cafe",
        "categoryName": "Cafe",
        "address": "1 Quay St, Falmouth",
        "phone": "+44 1326 000000",
        "website": "https://harbourtide.example",
        "totalScore": 4.6,
        "reviewsCount": 212,
        "reviewsDistribution": {
            "oneStar": 4,
            "twoStar": 3,
            "threeStar": 10,
            "fourStar": 45,
            "fiveStar": 150,
        },
        "openingHours": [
            {"day": "Monday", "hours": "8 AM to 5 PM"},
            {"day": "Sunday", "hours": "Closed"},
        ],
        "description": "Coffee by the harbour.",
        "url": PLACE,
        "reviews": [
            {
                "name": "Ana",
                "stars": 5,
                "publishedAtDate": "2026-09-01T12:00:00Z",
                "text": "Best view of the tide.",
                "responseFromOwnerText": "Thank you!",
            },
            {"name": "Ben", "stars": 3, "text": ""},
        ],
    } | changed


@pytest.mark.parametrize(
    "url",
    [PLACE, "https://maps.app.goo.gl/AbC123", "https://maps.google.com/?cid=123"],
)
def test_a_place_is_one_source(url: str) -> None:
    """A place page, a short link the plugin opens, or a place's `cid`."""
    assert PULLER.fit(urlsplit(url)) == Fit.ONE


def test_a_maps_search_is_many_places() -> None:
    """Refused in the dialog rather than pulled as one source."""
    url = "https://www.google.com/maps/search/cafes+falmouth"

    assert PULLER.fit(urlsplit(url)) == Fit.LIST


def test_a_google_search_page_is_not_a_place() -> None:
    """It is left to Web Crawl, as any page."""
    assert PULLER.fit(urlsplit("https://www.google.com/search?q=tides")) is None


def test_the_place_comes_with_its_details_and_reviews_in_one_call() -> None:
    """Reviews come inside the place, so there is no second call."""
    assert PULLER.calls(PLACE) == [
        ToolCall(
            "scrape",
            {
                "urls": [PLACE],
                "max_places": 1,
                "include_details": True,
                "max_reviews": 100,
            },
        )
    ]


def test_a_place_is_written_with_its_hours_and_reviews() -> None:
    """The owner's reply stays with the review it answers."""
    pulled = PULLER.written(PLACE, {"scrape": [place()]})

    assert pulled == Pulled(
        "Harbour Tide Cafe",
        """# Harbour Tide Cafe

- **Category:** Cafe
- **Address:** 1 Quay St, Falmouth
- **Phone:** +44 1326 000000
- **Website:** https://harbourtide.example
- **Rating:** 4.6 out of 5, from 212 reviews
- **Ratings:** 5 stars: 150, 4 stars: 45, 3 stars: 10, 2 stars: 3, 1 star: 4
- **Link:** https://www.google.com/maps/place/Harbour+Tide+Cafe/@50.1,-5.0,17z

## About

Coffee by the harbour.

## Opening hours

- Monday: 8 AM to 5 PM
- Sunday: Closed

## Reviews

- **Ana** (5 stars, 2026-09-01T12:00:00Z): Best view of the tide. Owner's reply: Thank you!
- **Ben** (3 stars): no text""",
    )


def test_a_closed_place_says_so() -> None:
    """A closed place is still kept, with that fact first."""
    pulled = PULLER.written(PLACE, {"scrape": [place(permanentlyClosed=True)]})

    assert pulled is not None
    assert "- **Status:** Permanently closed" in pulled.markdown


def test_a_place_the_plugin_could_not_open_is_nothing_to_keep() -> None:
    """A sign-in wall comes back as an error item, not a place."""
    assert PULLER.written(PLACE, {"scrape": [{"error": "sign_in_required"}]}) is None


def test_a_maps_search_is_listed_as_its_places() -> None:
    """A place's own link routes back here as one source."""
    search = "https://www.google.com/maps/search/cafes+falmouth"

    assert PULLER.listing is not None
    assert PULLER.listing.call(search, 20) == ToolCall(
        "scrape", {"urls": [search], "max_places": 20}
    )
    assert PULLER.listing.items([place()]) == [
        Listed(PLACE, "Harbour Tide Cafe", "Cafe · 1 Quay St, Falmouth")
    ]


def test_a_search_runs_on_google_maps_itself() -> None:
    """A place belongs in the words, "cafes in Falmouth", as on Maps."""
    assert PULLER.search is not None
    assert PULLER.search("cafes in Falmouth", 20) == ToolCall(
        "scrape", {"search_queries": ["cafes in Falmouth"], "max_places": 20}
    )
