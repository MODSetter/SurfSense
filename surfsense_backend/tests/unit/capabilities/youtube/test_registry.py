"""The youtube namespace registers each verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    youtube,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.youtube.comments.schemas import CommentsInput, CommentsOutput
from app.capabilities.youtube.scrape.schemas import ScrapeInput, ScrapeOutput

pytestmark = pytest.mark.unit


def test_youtube_scrape_is_registered_and_billable():
    cap = get_capability("youtube.scrape")

    assert cap.name == "youtube.scrape"
    assert cap.input_schema is ScrapeInput
    assert cap.output_schema is ScrapeOutput
    assert cap.billing_unit is BillingUnit.YOUTUBE_VIDEO


def test_youtube_comments_is_registered_and_billable():
    cap = get_capability("youtube.comments")

    assert cap.name == "youtube.comments"
    assert cap.input_schema is CommentsInput
    assert cap.output_schema is CommentsOutput
    assert cap.billing_unit is BillingUnit.YOUTUBE_COMMENT
