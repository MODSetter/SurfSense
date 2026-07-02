"""``web.discover`` I/O contract bounds."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.web.discover.schemas import DiscoverInput

pytestmark = pytest.mark.unit


def test_top_k_defaults_and_accepts_the_valid_range():
    assert DiscoverInput(query="q").top_k == 10
    assert DiscoverInput(query="q", top_k=1).top_k == 1
    assert DiscoverInput(query="q", top_k=50).top_k == 50


@pytest.mark.parametrize("bad", [0, -1, 51, 100])
def test_top_k_outside_1_to_50_is_rejected(bad):
    with pytest.raises(ValidationError):
        DiscoverInput(query="q", top_k=bad)
