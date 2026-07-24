"""``tiktok.user_search`` capability registration (billed per account; see config
``TIKTOK_MICROS_PER_USER``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.tiktok.user_search.executor import build_user_search_executor
from app.capabilities.tiktok.user_search.schemas import (
    UserSearchInput,
    UserSearchOutput,
)

TIKTOK_USER_SEARCH = Capability(
    name="tiktok.user_search",
    description=(
        "Find public TikTok accounts by keyword. Returns profile metadata "
        "(name, followers, bio, verification) per matching account."
    ),
    input_schema=UserSearchInput,
    output_schema=UserSearchOutput,
    executor=build_user_search_executor(),
    billing_unit=BillingUnit.TIKTOK_USER,
    docs_url="/docs/connectors/native/tiktok",
)

register_capability(TIKTOK_USER_SEARCH)
