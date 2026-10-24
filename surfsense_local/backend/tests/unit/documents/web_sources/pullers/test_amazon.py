from urllib.parse import urlsplit

import pytest

from modules.documents.web_sources.pullers.amazon import PULLER
from modules.documents.web_sources.pullers.puller import Fit, Listed, Pulled, ToolCall

pytestmark = pytest.mark.unit

PRODUCT = "https://www.amazon.com/Tide-Clock/dp/B0TIDE0001"


def product(**changed: object) -> dict:
    """A product page as the Amazon plugin's `scrape` answers it, with details."""
    return {
        "title": "Tide Clock",
        "url": PRODUCT,
        "asin": "B0TIDE0001",
        "brand": "Harbour Co",
        "price": {"value": 29.99, "currency": "$"},
        "stars": 4.4,
        "reviewsCount": 1280,
        "features": ["Shows high and low tide", "Battery lasts a year"],
        "description": "A wall clock that follows the tide.",
        "productOverview": [{"name": "Colour", "value": "Blue"}],
        "aiReviewsSummary": {"text": "Customers like how easy it is to read."},
        "productPageReviews": [
            {
                "title": "Accurate",
                "stars": 5.0,
                "text": "Matches the tide tables.",
                "author": "Ana",
                "date": "Reviewed in the UK on 2 September 2026",
                "verified": True,
            }
        ],
    } | changed


@pytest.mark.parametrize(
    "url",
    [PRODUCT, "https://amzn.to/3xyz", "https://www.amazon.co.uk/gp/product/B0TIDE0001"],
)
def test_a_product_is_one_source(url: str) -> None:
    """A product page, or a short link the plugin follows itself."""
    assert PULLER.fit(urlsplit(url)) == Fit.ONE


def test_a_search_page_is_many_products() -> None:
    """Refused in the dialog rather than pulled as one source."""
    url = "https://www.amazon.com/s?k=tide+clock"

    assert PULLER.fit(urlsplit(url)) == Fit.LIST


def test_the_product_comes_with_its_details() -> None:
    """Its reviews are the ones on the product page: the plugin reads no more."""
    assert PULLER.calls(PRODUCT) == [
        ToolCall("scrape", {"urls": [PRODUCT], "max_items": 1, "include_details": True})
    ]


def test_a_product_is_written_with_its_details_and_reviews() -> None:
    """Each part of the page under its own heading, so a question can find it."""
    pulled = PULLER.written(PRODUCT, {"scrape": [product()]})

    assert pulled == Pulled(
        "Tide Clock",
        """# Tide Clock

- **Brand:** Harbour Co
- **Price:** 29.99 $
- **Rating:** 4.4 out of 5, from 1,280 reviews
- **Link:** https://www.amazon.com/Tide-Clock/dp/B0TIDE0001

## About this item

- Shows high and low tide
- Battery lasts a year

## Description

A wall clock that follows the tide.

## Details

- Colour: Blue

## What customers say

Customers like how easy it is to read.

## Reviews

- **Ana** (5 stars, Reviewed in the UK on 2 September 2026, verified purchase): Accurate. Matches the tide tables.""",
    )


def test_a_product_the_plugin_could_not_open_is_nothing_to_keep() -> None:
    """The pull fails and says so, rather than keeping an empty source."""
    error = {"error": "not_found", "url": PRODUCT}

    assert PULLER.written(PRODUCT, {"scrape": [error]}) is None


def test_a_search_is_listed_as_its_products() -> None:
    """Cards only: a product's details are read when it is added."""
    search = "https://www.amazon.com/s?k=tide+clock"

    assert PULLER.listing is not None
    assert PULLER.listing.call(search, 20) == ToolCall(
        "scrape", {"urls": [search], "max_items": 20, "include_details": False}
    )
    assert PULLER.listing.items([product(), {"error": "blocked"}]) == [
        Listed(PRODUCT, "Tide Clock", "29.99 $ · 4.4 out of 5")
    ]


def test_a_search_runs_on_amazon_itself() -> None:
    """Cards only, as a search page's are; the plugin's own store."""
    assert PULLER.search is not None
    assert PULLER.search("tide clock", 20) == ToolCall(
        "scrape",
        {"search_terms": ["tide clock"], "max_items": 20, "include_details": False},
    )
