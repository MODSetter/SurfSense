"""``web.discover`` capability registration (free — see 04-capabilities open item)."""

from __future__ import annotations

from app.capabilities.store import register_capability
from app.capabilities.types import Capability
from app.capabilities.web.discover.executor import build_discover_executor
from app.capabilities.web.discover.schemas import DiscoverInput, DiscoverOutput

WEB_DISCOVER = Capability(
    name="web.discover",
    input_schema=DiscoverInput,
    output_schema=DiscoverOutput,
    executor=build_discover_executor(),
    billing_unit=None,
)

register_capability(WEB_DISCOVER)
