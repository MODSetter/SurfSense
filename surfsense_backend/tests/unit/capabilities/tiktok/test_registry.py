"""The tiktok namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    tiktok,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.tiktok.comments.schemas import CommentsInput, CommentsOutput
from app.capabilities.tiktok.scrape.schemas import ScrapeInput, ScrapeOutput
from app.capabilities.tiktok.trending.schemas import TrendingInput, TrendingOutput
from app.capabilities.tiktok.user_search.schemas import (
    UserSearchInput,
    UserSearchOutput,
)

pytestmark = pytest.mark.unit


def test_tiktok_scrape_is_registered_and_billed_per_video():
    cap = get_capability("tiktok.scrape")

    assert cap.name == "tiktok.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.TIKTOK_VIDEO


def test_tiktok_user_search_is_registered_and_billed_per_profile():
    cap = get_capability("tiktok.user_search")

    assert cap.name == "tiktok.user_search"
    assert cap.input_schema is UserSearchInput
    assert cap.output_schema is UserSearchOutput
    assert cap.billing_unit is BillingUnit.TIKTOK_USER


def test_tiktok_comments_is_registered_and_billed_per_comment():
    cap = get_capability("tiktok.comments")

    assert cap.name == "tiktok.comments"
    assert cap.input_schema is CommentsInput
    assert cap.output_schema is CommentsOutput
    assert cap.billing_unit is BillingUnit.TIKTOK_COMMENT


def test_tiktok_trending_is_registered_and_billed_per_video():
    cap = get_capability("tiktok.trending")

    assert cap.name == "tiktok.trending"
    assert cap.input_schema is TrendingInput
    assert cap.output_schema is TrendingOutput
    # Trending returns videos, so it shares the per-video meter.
    assert cap.billing_unit is BillingUnit.TIKTOK_VIDEO
