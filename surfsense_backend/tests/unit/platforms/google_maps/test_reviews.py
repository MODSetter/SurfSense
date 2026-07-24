"""Offline tests for the Google Maps reviews parsing + flow helpers.

``fixtures/boq_reviews_page.json`` is a real ``GetLocalBoqProxy`` page (the
raw review list, ``jd[1][10][2]``) captured by scripts/e2e_google_maps_scraper.py
step 7. Regenerate it with that script if Google shifts the structure.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.proprietary.platforms.google_maps.fetch import build_reviews_url
from app.proprietary.platforms.google_maps.parsers import (
    parse_review,
    parse_reviews_page,
    strip_personal_data,
)
from app.proprietary.platforms.google_maps.reviews import _before_cutoff, _keep

_FIXTURE = Path(__file__).parent / "fixtures" / "boq_reviews_page.json"


@pytest.fixture
def reviews_raw() -> list:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_parse_reviews_page_full_page(reviews_raw):
    parsed = parse_reviews_page(reviews_raw)
    assert len(parsed) == len(reviews_raw) == 10
    for review in parsed:
        assert review["name"]
        assert review["reviewId"]
        assert 1 <= review["stars"] <= 5
        assert review["publishedAtDate"].endswith("Z")


def test_parse_review_fields(reviews_raw):
    review = parse_review(reviews_raw[0])
    assert review["name"] == "Greg"
    assert review["stars"] == 5
    assert review["reviewerId"] == "108156147079988470963"
    assert review["reviewerUrl"].startswith("https://www.google.com/maps/contrib/")
    assert review["reviewerNumberOfReviews"] == 63
    assert review["isLocalGuide"] is True
    assert review["reviewOrigin"] == "Google"
    assert review["originalLanguage"] == "en"
    assert review["publishAt"] == "2 months ago"
    # 1776469524140 ms epoch -> UTC ISO
    assert review["publishedAtDate"] == "2026-04-17T23:45:24.140Z"
    assert "spiced" in review["text"]
    # Guided answers split into context vs per-aspect ratings.
    assert review["reviewContext"]["Order type"] == "Take out"
    assert review["reviewDetailedRating"]["Food"] == 5


def test_parse_review_owner_response_and_images(reviews_raw):
    with_reply = [
        r
        for r in (parse_review(x) for x in reviews_raw)
        if r and r.get("responseFromOwnerText")
    ]
    assert with_reply, "fixture should contain at least one owner reply"
    assert with_reply[0]["responseFromOwnerText"]

    with_images = [
        r
        for r in (parse_review(x) for x in reviews_raw)
        if r and r.get("reviewImageUrls")
    ]
    assert with_images, "fixture should contain at least one review with photos"
    assert with_images[0]["reviewImageUrls"][0].startswith("https://")


def test_parse_review_rejects_garbage():
    assert parse_review(None) is None
    assert parse_review([]) is None
    assert parse_review([None, 5]) is None  # no author block


def test_strip_personal_data(reviews_raw):
    review = parse_review(reviews_raw[0])
    strip_personal_data(review)
    for key in ("name", "reviewerId", "reviewerUrl", "reviewerPhotoUrl"):
        assert key not in review
    assert review["reviewId"]  # non-personal fields stay
    assert review["stars"] == 5


def test_before_cutoff():
    cutoff = datetime(2026, 3, 1)
    assert _before_cutoff({"publishedAtDate": "2026-02-01T00:00:00.000Z"}, cutoff)
    assert not _before_cutoff({"publishedAtDate": "2026-04-01T00:00:00.000Z"}, cutoff)
    assert not _before_cutoff({}, cutoff)  # undated reviews are kept


def test_keep_filters():
    review = {"text": "Great NOODLES here", "reviewOrigin": "Google"}
    assert _keep(review, filter_string="", origin="all")
    assert _keep(review, filter_string="noodles", origin="google")
    assert not _keep(review, filter_string="pizza", origin="all")
    assert not _keep({"reviewOrigin": "TripAdvisor"}, filter_string="", origin="google")


def test_build_reviews_url_shape():
    fid = "0x89c3ca9c11f90c25:0x6cc8dba851799f09"
    first = build_reviews_url(fid, sort_code=2)
    assert "GetLocalBoqProxy" in first
    assert "hl=en" in first
    assert fid in json.dumps(first) or "0x89c3ca9c11f90c25" in first
    # First page requests a page size; later pages carry the token instead.
    paged = build_reviews_url(fid, sort_code=2, page_token="TOKEN123")
    assert "TOKEN123" in paged
    assert paged != first
