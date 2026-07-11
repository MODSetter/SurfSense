"""The instagram namespace registers its verbs for the doors/agent to read.

Unlike the stale reddit assertion (``billing_unit is None``), these assert the
real meters — the Capability definitions are the source of truth.
"""

from __future__ import annotations

import pytest

from app.capabilities import (
    instagram,  # noqa: F401  — importing the namespace registers its verbs
)
from app.capabilities.core.store import get_capability
from app.capabilities.core.types import BillingUnit

pytestmark = pytest.mark.unit


def test_instagram_scrape_registered_with_item_meter():
    cap = get_capability("instagram.scrape")
    assert cap.name == "instagram.scrape"
    assert cap.billing_unit is BillingUnit.INSTAGRAM_ITEM


def test_instagram_details_registered_with_item_meter():
    cap = get_capability("instagram.details")
    assert cap.name == "instagram.details"
    assert cap.billing_unit is BillingUnit.INSTAGRAM_ITEM
