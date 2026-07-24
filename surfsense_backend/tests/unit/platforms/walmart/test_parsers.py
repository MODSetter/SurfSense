from __future__ import annotations

from pathlib import Path

from app.proprietary.platforms.walmart.fetch import is_blocked
from app.proprietary.platforms.walmart.next_data import extract_next_data
from app.proprietary.platforms.walmart.parsers import (
    parse_listing_page,
    parse_product,
    parse_reviews_page,
)
from app.proprietary.platforms.walmart.url_resolver import extract_item_id, resolve_url

_FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_product_parser_extracts_core_fields_and_review_sample():
    data = extract_next_data(_fixture("product.html"))
    item = parse_product(data, url="https://www.walmart.com/ip/212092810")

    assert item["usItemId"] == "212092810"
    assert item["name"].startswith("Midea")
    assert item["price"] == {"value": 149.0, "currency": "USD"}
    assert item["listPrice"] == {"value": 199.0, "currency": "USD"}
    assert item["stars"] == 4.5
    assert item["reviewsCount"] == 6287
    assert item["inStock"] is True
    assert item["seller"] == {"id": "F55CT", "name": "Walmart.com", "type": "WALMART"}
    assert item["longDescription"] == "<p>A powerful window unit.</p>"
    assert item["images"] == [
        "https://i5.walmartimages.com/1.jpg",
        "https://i5.walmartimages.com/2.jpg",
    ]
    # Walmart ships category.path as breadcrumb objects, not a string.
    assert item["breadCrumbs"] == ["Home", "Air Conditioners"]
    assert item["category"] == "Air Conditioners"
    assert item["reviewsSample"]["totalReviewCount"] == 6287
    assert item["reviewsSample"]["topReviews"][0]["verifiedPurchase"] is True


def test_listing_parser_normalizes_cards_and_marketplace_seller():
    data = extract_next_data(_fixture("listing.html"))
    cards = parse_listing_page(data)

    assert [c["usItemId"] for c in cards] == ["791595618", "999001"]
    first = cards[0]
    assert first["url"] == "https://www.walmart.com/ip/Acer-Chromebook/791595618"
    assert first["price"] == {"value": 79.99, "currency": "USD"}
    assert first["seller"]["type"] == "MARKETPLACE"
    assert first["inStock"] is True
    # Fallback price + out-of-stock derivation for the second card.
    assert cards[1]["price"] == {"value": 499.0}
    assert cards[1]["inStock"] is False


def test_reviews_parser_extracts_all_records():
    data = extract_next_data(_fixture("reviews.html"))
    reviews = parse_reviews_page(data)

    assert len(reviews) == 2
    assert reviews[0]["reviewId"] == "296013686"
    assert reviews[0]["author"] == "JohnPaul"
    assert reviews[0]["verifiedPurchase"] is True
    assert reviews[0]["images"] == ["https://i5.walmartimages.com/r.jpg"]
    assert reviews[0]["sellerResponse"] == "Thanks for the review!"
    assert reviews[1]["verifiedPurchase"] is False


def test_block_detection_handles_status_and_body():
    assert is_blocked(_fixture("blocked.html"), 200)
    assert is_blocked("", 412)
    assert is_blocked("", 429)
    assert not is_blocked(_fixture("product.html"), 200)


def test_missing_next_data_yields_none():
    assert extract_next_data("<html><body>no script here</body></html>") is None
    assert parse_product(extract_next_data("") or {}, url="x") == {}


def test_url_resolver_classifies_and_extracts_ids():
    assert resolve_url("https://www.walmart.com/ip/Foo/123456789").kind == "product"
    assert (
        extract_item_id("https://www.walmart.com/reviews/product/212092810")
        == "212092810"
    )
    assert resolve_url("https://www.walmart.com/search?q=tv").kind == "listing"
    assert resolve_url("https://www.walmart.com/cp/tvs/3944").kind == "listing"
    assert resolve_url("https://example.com/ip/1") is None
