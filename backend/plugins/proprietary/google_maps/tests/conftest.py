"""Shared test setup for the Google Maps plugin."""

import pytest

from proprietary.google_maps import fetch


@pytest.fixture(autouse=True)
def _empty_fid_cache():
    """The placeId -> fid cache lives for the process; no test sees another's."""
    fetch._fid_by_place_id.clear()
    yield
    fetch._fid_by_place_id.clear()
