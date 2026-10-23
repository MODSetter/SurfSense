"""Offline tests for the Google Maps reviews parsing + flow helpers.

``fixtures/boq_reviews_page.json`` is a real ``GetLocalBoqProxy`` page (the
raw review list, ``jd[1][10][2]``) captured by scripts/e2e_google_maps_scraper.py
step 7. Regenerate it with that script if Google shifts the structure.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from proprietary.google_maps.fetch import build_reviews_url
from proprietary.google_maps.parsers import (
    parse_review,
    parse_reviews_page,
    strip_personal_data,
)
from proprietary.google_maps.reviews import _before_cutoff, _keep

_FIXTURE = Path(__file__).parent / "fixtures" / "boq_reviews_page.json"


@pytest.fixture
def reviews_raw() -> list:
    if not _FIXTURE.exists():
        pytest.skip("captured Google response not in the repo")
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


_BIRD_BRANCH = Path(__file__).parent / "fixtures" / "reviews_birdbranch_page.json"


@pytest.fixture
def bird_branch() -> list:
    # Live GetLocalBoqProxy reviews (hl=en) for Bird & Branch, 2026-10-14:
    # 2 Spanish (translated), 3 truncated English, 3 rating-only (one with an
    # owner reply). Reviewer names, photos and contributor ids are replaced.
    return json.loads(_BIRD_BRANCH.read_text(encoding="utf-8"))


def test_bird_branch_capture_keeps_no_review_tokens(bird_branch):
    # r[48][1] is a signed per-request token for the review's actions.
    assert {raw[48][1] for raw in bird_branch} == {"TOKEN"}


def test_translation_comes_from_slot_37_in_the_request_language(bird_branch):
    spanish = parse_review(bird_branch[2], "en")
    assert spanish["originalLanguage"] == "es"
    assert spanish["textTranslated"].startswith("The coffee was very good")
    assert spanish["translatedLanguage"] == "en"
    assert spanish["text"].startswith("El caf")


def test_truncated_preview_is_never_a_translation(bird_branch):
    # r[28] is r[27] cut short with an ellipsis when r[29] == 1.
    for raw in bird_branch[1:5]:
        if raw[26] != "en":
            continue
        assert raw[29] == 1 and raw[28].endswith("…")
        review = parse_review(raw, "en")
        assert "textTranslated" not in review
        assert "translatedLanguage" not in review
        assert not review["text"].endswith("…")


def test_line_breaks_are_newlines_not_html(bird_branch):
    spanish = parse_review(bird_branch[0], "en")
    assert "<br>" in bird_branch[0][27]
    assert "<br" not in spanish["text"] and "\n" in spanish["text"]
    assert "<br" not in spanish["textTranslated"]

    reply = list(bird_branch[3])
    reply[4] = list(reply[4])
    reply[4][2] = "Thanks!<br><br>See you soon &amp; take care<br/>"
    parsed = parse_review(reply, "en")
    assert parsed["responseFromOwnerText"] == "Thanks!\n\nSee you soon & take care"


def test_rating_only_reviews_have_no_text_or_language(bird_branch):
    for raw in bird_branch[5:]:
        assert raw[27] == "" and raw[26] == ""
        review = parse_review(raw, "en")
        assert review["stars"]
        assert "text" not in review
        assert "originalLanguage" not in review
    # The owner's reply on a rating-only review still comes through.
    assert parse_review(bird_branch[7], "en")["responseFromOwnerText"]


def test_translation_into_another_request_language():
    # hl=fr: Google translates the English review into French in r[37].
    raw: list = [None] * 48
    raw[1] = 5
    raw[3] = ["Ada", None, "https://www.google.com/maps/contrib/42", 3, 0, [None, 0]]
    raw[26] = "en"
    raw[27] = "Everything was so great."
    raw[36] = "anglais"
    raw[37] = "Tout était excellent."
    review = parse_review(raw, "fr")
    assert review["textTranslated"] == "Tout était excellent."
    assert review["translatedLanguage"] == "fr"
    raw[37] = None
    assert "translatedLanguage" not in parse_review(raw, "fr")


def test_parse_reviews_page_passes_the_language_on(bird_branch):
    parsed = parse_reviews_page(bird_branch, "en")
    assert len(parsed) == len(bird_branch)
    translated = [r for r in parsed if r.get("textTranslated")]
    assert len(translated) == 2
    assert {r["translatedLanguage"] for r in translated} == {"en"}
