from urllib.parse import urlsplit

import pytest

from modules.documents.web_sources.pullers.puller import Fit, Listed, Pulled, ToolCall
from modules.documents.web_sources.pullers.walmart import PULLER

pytestmark = pytest.mark.unit

PRODUCT = "https://www.walmart.com/ip/Tide-Clock/123456"


def product(**changed: object) -> dict:
    """A product as the Walmart plugin's `scrape` answers it, with details."""
    return {
        "name": "Tide Clock",
        "brand": "Harbour Co",
        "url": PRODUCT,
        "price": {"value": 27.5, "currency": "USD"},
        "stars": 4.2,
        "reviewsCount": 87,
        "shortDescription": "A clock that follows the tide.",
        "longDescription": "<p>Shows <b>high</b> and low tide.</p><ul><li>Blue</li><li>Wall mount</li></ul>",
        "specifications": {"Colour": "Blue", "Battery": "AA"},
    } | changed


REVIEWS = [
    {
        "rating": 4,
        "title": "Nice",
        "text": "Looks great in the kitchen.",
        "author": "Ana",
        "submissionTime": "2026-08-12",
    }
]


@pytest.mark.parametrize("url", [PRODUCT, "https://www.walmart.com/ip/123456"])
def test_a_product_is_one_source(url: str) -> None:
    """A product page, with or without its slug."""
    assert PULLER.fit(urlsplit(url)) == Fit.ONE


def test_a_search_page_is_many_products() -> None:
    """Refused in the dialog rather than pulled as one source."""
    url = "https://www.walmart.com/search?q=tide+clock"

    assert PULLER.fit(urlsplit(url)) == Fit.LIST


def test_the_product_comes_with_its_most_helpful_reviews() -> None:
    """The reviews are optional: a product with none is still a source."""
    assert PULLER.calls(PRODUCT) == [
        ToolCall(
            "scrape",
            {
                "urls": [PRODUCT],
                "max_items": 1,
                "include_details": True,
                "include_reviews_sample": False,
            },
        ),
        ToolCall(
            "reviews",
            {"urls": [PRODUCT], "max_reviews": 100, "sort_by": "most-helpful"},
            optional=True,
        ),
    ]


def test_a_product_is_written_with_its_description_as_text_and_reviews() -> None:
    """Walmart's HTML description is kept as text, its list as bullets."""
    pulled = PULLER.written(PRODUCT, {"scrape": [product()], "reviews": REVIEWS})

    assert pulled == Pulled(
        "Tide Clock",
        """# Tide Clock

- **Brand:** Harbour Co
- **Price:** 27.5 USD
- **Rating:** 4.2 out of 5, from 87 reviews
- **Link:** https://www.walmart.com/ip/Tide-Clock/123456

## Description

A clock that follows the tide.

Shows high and low tide.
- Blue
- Wall mount

## Specifications

- Colour: Blue
- Battery: AA

## Reviews

- **Ana** (4 stars, 2026-08-12): Nice. Looks great in the kitchen.""",
    )


def test_a_product_the_plugin_could_not_open_is_nothing_to_keep() -> None:
    """A blocked page comes back as an error item, not a product."""
    error = {"error": "blocked", "input": PRODUCT}

    assert PULLER.written(PRODUCT, {"scrape": [error], "reviews": []}) is None


def test_a_search_is_listed_as_its_products() -> None:
    """Cards only: a product's details are read when it is added."""
    search = "https://www.walmart.com/search?q=tide+clock"

    assert PULLER.listing is not None
    assert PULLER.listing.call(search, 20) == ToolCall(
        "scrape",
        {
            "urls": [search],
            "max_items": 20,
            "include_details": False,
            "include_reviews_sample": False,
        },
    )
    assert PULLER.listing.items([product()]) == [
        Listed(PRODUCT, "Tide Clock", "27.5 USD · 4.2 out of 5")
    ]


def test_a_search_runs_on_walmart_itself() -> None:
    """Cards only, as a search page's are."""
    assert PULLER.search is not None
    assert PULLER.search("tide clock", 20) == ToolCall(
        "scrape",
        {
            "search_terms": ["tide clock"],
            "max_items": 20,
            "include_details": False,
            "include_reviews_sample": False,
        },
    )
