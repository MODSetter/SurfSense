"""``instagram.*`` input guards: source exclusivity and bounded batches."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.instagram.comments.schemas import CommentsInput
from app.capabilities.instagram.details.schemas import DetailsInput, DetailsOutput
from app.capabilities.instagram.scrape.schemas import (
    MAX_INSTAGRAM_ITEMS,
    MAX_INSTAGRAM_SOURCES,
    ScrapeInput,
)

pytestmark = pytest.mark.unit


def test_scrape_rejects_no_source():
    with pytest.raises(ValidationError):
        ScrapeInput()


def test_scrape_rejects_both_sources():
    with pytest.raises(ValidationError):
        ScrapeInput(urls=["https://www.instagram.com/natgeo/"], search_queries=["fit"])


def test_scrape_accepts_urls_only():
    payload = ScrapeInput(urls=["https://www.instagram.com/natgeo/"])
    assert payload.search_queries == []
    assert payload.estimated_units == payload.max_items


def test_scrape_bounds():
    with pytest.raises(ValidationError):
        ScrapeInput(
            urls=["https://www.instagram.com/x/"],
            max_items=MAX_INSTAGRAM_ITEMS + 1,
        )
    with pytest.raises(ValidationError):
        ScrapeInput(
            urls=[
                f"https://www.instagram.com/u{i}/"
                for i in range(MAX_INSTAGRAM_SOURCES + 1)
            ]
        )


def test_comments_requires_urls_and_caps_at_50():
    with pytest.raises(ValidationError):
        CommentsInput(urls=[])
    with pytest.raises(ValidationError):
        CommentsInput(
            urls=["https://www.instagram.com/p/Cabc/"], max_comments_per_post=51
        )
    ok = CommentsInput(
        urls=["https://www.instagram.com/p/Cabc/"], max_comments_per_post=50
    )
    assert ok.max_comments_per_post == 50


def test_details_discriminated_union_selects_by_detail_kind():
    out = DetailsOutput(
        items=[
            {"detailKind": "profile", "username": "natgeo"},
            {"detailKind": "hashtag", "name": "fit"},
            {"detailKind": "place", "name": "Copenhagen"},
        ]
    )
    kinds = [type(i).__name__ for i in out.items]
    assert kinds == ["InstagramProfile", "InstagramHashtag", "InstagramPlace"]
    assert out.billable_units == 3


def test_details_rejects_both_sources():
    with pytest.raises(ValidationError):
        DetailsInput(
            urls=["https://www.instagram.com/natgeo/"], search_queries=["x"]
        )
