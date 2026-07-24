"""``youtube.comments`` input guards: URLs required and batch/count bounded."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.youtube.comments.schemas import (
    MAX_COMMENT_VIDEOS,
    CommentsInput,
)

pytestmark = pytest.mark.unit


def test_rejects_empty_url_batch():
    with pytest.raises(ValidationError):
        CommentsInput(urls=[])


def test_rejects_batch_over_the_cap():
    too_many = [f"https://youtu.be/{i}" for i in range(MAX_COMMENT_VIDEOS + 1)]
    with pytest.raises(ValidationError):
        CommentsInput(urls=too_many)


def test_defaults_max_comments_and_newest_first():
    payload = CommentsInput(urls=["https://youtu.be/abc"])
    assert payload.max_comments == 20
    assert payload.sort_by == "NEWEST_FIRST"


def test_rejects_zero_max_comments():
    with pytest.raises(ValidationError):
        CommentsInput(urls=["https://youtu.be/abc"], max_comments=0)
