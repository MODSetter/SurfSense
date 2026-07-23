"""``HttpUrlStr`` boundary type: accept well-formed http(s) URLs, reject the rest."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.capabilities.core.validation import HttpUrlStr

pytestmark = pytest.mark.unit


class _Model(BaseModel):
    urls: list[HttpUrlStr]


def test_accepts_http_and_https_urls_unchanged() -> None:
    model = _Model(urls=["https://example.com/path?q=1", "http://a.co"])
    assert model.urls == ["https://example.com/path?q=1", "http://a.co"]


def test_trims_surrounding_whitespace() -> None:
    assert _Model(urls=["  https://example.com  "]).urls == ["https://example.com"]


@pytest.mark.parametrize(
    "bad",
    ["not-a-url", "example.com", "ftp://example.com", "http://", "javascript:alert(1)"],
)
def test_rejects_malformed_or_non_http_urls(bad: str) -> None:
    with pytest.raises(ValidationError):
        _Model(urls=[bad])
