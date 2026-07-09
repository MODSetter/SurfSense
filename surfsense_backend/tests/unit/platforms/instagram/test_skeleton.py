"""Offline skeleton tests: input surface parity + URL classification.

No network. Locks the two invariants the reference-compatible surface promises —
no auth fields ever, and additive ``extra="allow"`` parity — plus the full
``url_resolver`` classification/normalization table (``_u/`` and profilecard
stripping, story→profile, ID-only locations, numeric post-ID flagging).
"""

from __future__ import annotations

from app.proprietary.platforms.instagram.schemas import (
    InstagramMediaItem,
    InstagramScrapeInput,
)
from app.proprietary.platforms.instagram.url_resolver import resolve_url


def test_input_has_no_auth_fields():
    # Anonymous-only: the input surface must never expose a login/credential seam.
    forbidden = {
        "sessionid",
        "username",
        "password",
        "cookies",
        "authorization",
        "proxyConfiguration",
        "loginCredentials",
    }
    assert forbidden.isdisjoint(InstagramScrapeInput.model_fields)


def test_input_defaults():
    model = InstagramScrapeInput()
    assert model.resultsType == "posts"
    assert model.searchType == "hashtag"
    assert model.directUrls == []
    assert model.addParentData is False


def test_input_allows_extra_inert_fields():
    # A reference field the acquisition layer doesn't source is accepted, not rejected.
    model = InstagramScrapeInput(enhanceUserSearchWithFacebookPage="x")
    assert model.model_dump().get("enhanceUserSearchWithFacebookPage") == "x"


def test_media_item_to_output_keeps_none_keys():
    out = InstagramMediaItem(id="123", shortCode="abc").to_output()
    assert out["id"] == "123"
    assert out["shortCode"] == "abc"
    # Unsourced fields stay present as None / [] for additive parity.
    assert out["likesCount"] is None
    assert out["requestErrorMessages"] == []


def test_resolve_profile():
    r = resolve_url("https://www.instagram.com/natgeo/")
    assert r.kind == "profile"
    assert r.value == "natgeo"


def test_resolve_bare_profile_id():
    r = resolve_url("natgeo")
    assert r.kind == "profile" and r.value == "natgeo"


def test_resolve_post_and_reel():
    r = resolve_url("https://www.instagram.com/p/Cabc123/")
    assert r.kind == "post" and r.value == "Cabc123" and r.numeric_post_id is False
    r = resolve_url("https://www.instagram.com/reel/Cxyz/")
    assert r.kind == "reel" and r.value == "Cxyz"


def test_resolve_hashtag():
    r = resolve_url("https://www.instagram.com/explore/tags/crossfit/")
    assert r.kind == "hashtag" and r.value == "crossfit"


def test_resolve_place_with_slug_and_id_only():
    with_slug = resolve_url(
        "https://www.instagram.com/explore/locations/7538318/copenhagen/"
    )
    assert with_slug.kind == "place" and with_slug.value == "7538318"
    assert with_slug.slug == "copenhagen"
    id_only = resolve_url("https://www.instagram.com/explore/locations/7538318/")
    assert id_only.kind == "place" and id_only.value == "7538318"


def test_resolve_strips_u_and_profilecard():
    stripped_u = resolve_url("https://www.instagram.com/_u/natgeo/")
    assert stripped_u.kind == "profile" and stripped_u.value == "natgeo"
    card = resolve_url("https://www.instagram.com/natgeo/profilecard/")
    assert card.kind == "profile" and card.value == "natgeo"


def test_resolve_story_reduces_to_profile():
    r = resolve_url("https://www.instagram.com/stories/natgeo/12345/")
    assert r.kind == "profile" and r.value == "natgeo"


def test_resolve_numeric_post_id_flagged():
    r = resolve_url("https://www.instagram.com/p/12345/")
    assert r.kind == "post" and r.numeric_post_id is True


def test_resolve_rejects_non_instagram_host():
    assert resolve_url("https://example.com/natgeo/") is None
