"""Offline tests for the map-search flow: response extraction, URL building,
and the Apify result filters. The fixture is a real ``search?tbm=map`` response
captured by scripts/e2e_google_maps_scraper.py (step 9, query "pizza new york").
"""

import json
from pathlib import Path

import pytest

from app.proprietary.scrapers.google_maps.fetch import (
    _search_darrays,
    build_search_url,
)
from app.proprietary.scrapers.google_maps.parsers import parse_place
from app.proprietary.scrapers.google_maps.schemas import GoogleMapsScrapeInput
from app.proprietary.scrapers.google_maps.scraper import (
    _custom_point,
    _location_text,
    _passes_filters,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "search_response.json"


@pytest.fixture(scope="module")
def search_jd():
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_search_darrays_extracts_full_page(search_jd):
    darrays = _search_darrays(search_jd)
    assert len(darrays) == 20
    parsed = [parse_place(d) for d in darrays]
    for fields in parsed:
        assert fields["title"]
        assert fields["fid"].startswith("0x")
        assert fields["placeId"].startswith("ChIJ")
        assert "location" in fields
    fids = [f["fid"] for f in parsed]
    assert len(set(fids)) == 20  # no dupes within a page


def test_search_result_has_detail_fields(search_jd):
    fields = parse_place(_search_darrays(search_jd)[0])
    # Search entries carry the full darray, so detail fields come through.
    assert fields["categories"]
    assert fields["address"]
    assert fields["totalScore"] > 0
    assert fields["city"]


def test_search_darrays_rejects_garbage():
    assert _search_darrays(None) == []
    assert _search_darrays([]) == []
    assert _search_darrays([[None, None]]) == []


def test_build_search_url_shape():
    url = build_search_url("pizza new york", offset=20, language="de")
    assert url.startswith("https://www.google.com/search?tbm=map")
    assert "hl=de" in url
    assert "q=pizza%20new%20york" in url
    assert "!8i20" in url  # offset
    assert "!7i20" in url  # page size
    # whole-earth viewport when no coordinates given
    assert "!1d25000000" in url

    geo_url = build_search_url("museum", lat=48.85, lng=2.35, radius_m=5000)
    assert "!2d2.35" in geo_url and "!3d48.85" in geo_url
    assert "!1d10000" in geo_url  # radius -> diameter


def test_location_text_prefers_location_query():
    assert (
        _location_text(GoogleMapsScrapeInput(locationQuery="Berlin, Germany"))
        == "Berlin, Germany"
    )
    assert (
        _location_text(
            GoogleMapsScrapeInput(city="Austin", state="TX", countryCode="US")
        )
        == "Austin, TX, US"
    )
    assert _location_text(GoogleMapsScrapeInput()) is None


def test_custom_point():
    lat, lng, radius = _custom_point(
        GoogleMapsScrapeInput(
            customGeolocation={
                "type": "Point",
                "coordinates": [2.35, 48.85],
                "radiusKm": 5,
            }
        )
    )
    assert (lat, lng, radius) == (48.85, 2.35, 5000)
    assert _custom_point(GoogleMapsScrapeInput()) == (None, None, None)
    assert _custom_point(
        GoogleMapsScrapeInput(customGeolocation={"type": "Polygon"})
    ) == (None, None, None)


def test_passes_filters():
    fields = {
        "title": "Joe's Pizza",
        "categories": ["Pizza restaurant"],
        "totalScore": 4.4,
        "website": "https://joes.example",
    }
    default = GoogleMapsScrapeInput()
    assert _passes_filters(fields, "pizza", default)

    assert not _passes_filters(
        fields, "pizza", GoogleMapsScrapeInput(searchMatching="only_exact")
    )
    assert _passes_filters(
        fields, "pizza", GoogleMapsScrapeInput(searchMatching="only_includes")
    )
    assert not _passes_filters(
        fields, "burger", GoogleMapsScrapeInput(searchMatching="only_includes")
    )

    assert _passes_filters(
        fields, "pizza", GoogleMapsScrapeInput(categoryFilterWords=["pizza"])
    )
    assert not _passes_filters(
        fields, "pizza", GoogleMapsScrapeInput(categoryFilterWords=["barber"])
    )

    assert not _passes_filters(
        fields, "pizza", GoogleMapsScrapeInput(placeMinimumStars="fourAndHalf")
    )
    assert _passes_filters(
        fields, "pizza", GoogleMapsScrapeInput(placeMinimumStars="four")
    )

    assert _passes_filters(
        fields, "pizza", GoogleMapsScrapeInput(website="withWebsite")
    )
    assert not _passes_filters(
        fields, "pizza", GoogleMapsScrapeInput(website="withoutWebsite")
    )

    closed = {**fields, "permanentlyClosed": True}
    assert not _passes_filters(
        closed, "pizza", GoogleMapsScrapeInput(skipClosedPlaces=True)
    )
    assert _passes_filters(closed, "pizza", default)
