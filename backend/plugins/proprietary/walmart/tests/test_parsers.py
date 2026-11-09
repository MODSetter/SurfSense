from __future__ import annotations

import json
from pathlib import Path

import pytest

from proprietary.walmart.fetch import _blocked
from proprietary.walmart.next_data import extract_next_data
from proprietary.walmart.parsers import (
    parse_listing_page,
    parse_product,
    parse_reviews_meta,
    parse_reviews_page,
)
from proprietary.walmart.tests.fake_http import raw
from proprietary.walmart.url_resolver import extract_item_id, resolve_url

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


_PRODUCT_URL = "https://www.walmart.com/ip/212092810"


def test_block_detection_scans_the_body():
    assert _blocked(raw(_PRODUCT_URL, _fixture("blocked.html")))
    assert not _blocked(raw(_PRODUCT_URL, _fixture("product.html")))


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


def test_variant_product_takes_its_rating_from_the_reviews_node():
    """A VARIANT page has 0/0 on the product node; a 0 never beats the real figures."""
    data = extract_next_data(_fixture("product_variant.html"))
    item = parse_product(data, url="https://www.walmart.com/ip/8886020987")

    assert item["stars"] == 4.6
    assert item["reviewsCount"] == 68572


def test_a_product_with_no_reviews_still_reads_as_zero():
    data = extract_next_data(_fixture("product.html"))
    initial = data["props"]["pageProps"]["initialData"]["data"]
    initial["product"].update(averageRating=0, numberOfReviews=0)
    del initial["reviews"]
    item = parse_product(data, url="https://www.walmart.com/ip/212092810")

    assert (item["stars"], item["reviewsCount"]) == (0, 0)


def test_product_parser_maps_specifications_and_fulfillment():
    data = extract_next_data(_fixture("product_variant.html"))
    item = parse_product(data, url="https://www.walmart.com/ip/8886020987")

    assert item["specifications"] == {
        "Count per pack": "108",
        "Sheets": "648",
        "Number of rolls": "6",
    }
    assert item["fulfillment"]["shipping"] == {
        "availabilityStatus": "IN_STOCK",
        "availabilityType": "CURRENT",
        "isLowInStock": False,
        "maxOrderQuantity": 12,
        "location": "Bentonville, 72712",
        "badge": "Today",
        "deliveryDate": "2026-10-14T21:59:00.000Z",
        "selected": True,
    }
    assert item["fulfillment"]["pickup"]["deliveryDate"] == (
        "2026-10-14T09:00:00.000-04:00"
    )


def test_listing_variant_card_has_no_rating_rather_than_zero():
    """The card's {0, 0} rating node is not a rating."""
    cards = parse_listing_page(extract_next_data(_fixture("listing_variant.html")))

    variant, regular = cards
    assert (variant["stars"], variant["reviewsCount"]) == (None, None)
    assert (regular["stars"], regular["reviewsCount"]) == (4.7, 1823)


def test_reviews_name_the_variant_each_review_is_about():
    data = extract_next_data(_fixture("reviews_variant.html"))
    reviews = parse_reviews_page(data)

    assert [r["reviewedItemId"] for r in reviews] == ["391706535", "938805589"]
    assert reviews[1]["reviewedItemName"].startswith("Crest Toothpaste")


def test_reviews_meta_reads_the_last_page_past_the_gap():
    data = extract_next_data(_fixture("reviews_variant.html"))

    assert parse_reviews_meta(data) == {"lastPage": 229, "filteredCount": 2281}
    assert parse_reviews_meta(extract_next_data(_fixture("reviews.html"))) == {
        "lastPage": None,
        "filteredCount": None,
    }


@pytest.mark.parametrize("status", [403, 412, 429, 444, 503])
def test_edge_blocks_by_status_are_blocks(status):
    assert _blocked(raw(_PRODUCT_URL, status=status))


def test_a_missing_page_is_not_a_block():
    assert not _blocked(raw(_PRODUCT_URL, status=404))


def test_hidden_json_with_a_lone_surrogate_still_parses_and_serialises():
    """orjson refuses a lone surrogate escape (one review's broken emoji); the
    page must not be lost for it, nor the result fail to serialise."""
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        r'{"props": {"text": "broken \ud83d emoji", "ok": "😀"}}'
        "</script>"
    )

    data = extract_next_data(html)

    assert data is not None
    assert data["props"] == {"text": "broken � emoji", "ok": "\U0001f600"}
    json.dumps(data, ensure_ascii=False).encode()
