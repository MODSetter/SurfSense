"""``Capability`` registry contracts shared by every verb."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from pydantic import BaseModel
    from sqlalchemy.ext.asyncio import AsyncSession


class BillingUnit(StrEnum):
    """The meter a verb charges on (priced by the billing service, 03c). ``None`` = free.

    Each value doubles as the ``TokenUsage.usage_type`` audit string for that meter.
    """

    WEB_CRAWL = "web_crawl"
    REDDIT_ITEM = "reddit_item"
    GOOGLE_SEARCH_SERP = "google_search_serp"
    GOOGLE_MAPS_PLACE = "google_maps_place"
    GOOGLE_MAPS_REVIEW = "google_maps_review"
    AMAZON_PRODUCT = "amazon_product"
    YOUTUBE_VIDEO = "youtube_video"
    YOUTUBE_COMMENT = "youtube_comment"
    INSTAGRAM_ITEM = "instagram_item"
    INSTAGRAM_COMMENT = "instagram_comment"
    TIKTOK_VIDEO = "tiktok_video"
    TIKTOK_USER = "tiktok_user"
    TIKTOK_COMMENT = "tiktok_comment"
    INDEED_JOB = "indeed_job"
    WALMART_PRODUCT = "walmart_product"
    WALMART_REVIEW = "walmart_review"


class BillableInput(Protocol):
    """A billed verb's input that reports its worst-case unit count for pre-flight."""

    @property
    def estimated_units(self) -> int: ...


class BillableOutput(Protocol):
    """A capability output that reports its own billable count."""

    @property
    def billable_units(self) -> int: ...


@dataclass(frozen=True)
class CapabilityContext:
    """Request-scoped deps a capability call needs beyond its typed input."""

    session: AsyncSession
    workspace_id: int


Executor = Callable[[Any], Awaitable[Any]]


ActivityCategory = Literal["file", "research", "artifact", "connector", "action"]
_ACTIVITY_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


@dataclass(frozen=True, slots=True)
class ActivityDescriptor:
    """Trusted, backend-authored presentation metadata for an agent tool."""

    active_title: str
    completed_title: str
    category: ActivityCategory
    icon_key: str
    integration_key: str | None = None
    kind: str | None = None
    lifecycle: Literal["invocation", "phase"] = "invocation"
    visibility: Literal["show", "hide"] = "show"

    def as_metadata(self, *, kind: str | None = None) -> dict[str, str]:
        metadata = {
            "active_title": self.active_title,
            "completed_title": self.completed_title,
            "category": self.category,
            "icon_key": self.icon_key,
        }
        if resolved_kind := kind or self.kind:
            metadata["kind"] = resolved_kind
        if self.lifecycle != "invocation":
            metadata["lifecycle"] = self.lifecycle
        if self.visibility != "show":
            metadata["visibility"] = self.visibility
        if self.integration_key:
            metadata["integration_key"] = self.integration_key
        return metadata

    @classmethod
    def from_metadata(cls, value: object) -> ActivityDescriptor | None:
        """Accept only complete, bounded backend tool metadata."""
        if not isinstance(value, Mapping):
            return None
        active = value.get("active_title")
        completed = value.get("completed_title")
        category = value.get("category")
        icon_key = value.get("icon_key")
        integration_key = value.get("integration_key")
        kind = value.get("kind")
        lifecycle = value.get("lifecycle", "invocation")
        visibility = value.get("visibility", "show")
        if not (
            isinstance(active, str)
            and 0 < len(active.strip()) <= 120
            and isinstance(completed, str)
            and 0 < len(completed.strip()) <= 120
            and category in {"file", "research", "artifact", "connector", "action"}
            and isinstance(icon_key, str)
            and _ACTIVITY_KEY_RE.fullmatch(icon_key.strip())
            and (
                integration_key is None
                or (
                    isinstance(integration_key, str)
                    and _ACTIVITY_KEY_RE.fullmatch(integration_key.strip())
                )
            )
            and (
                kind is None
                or (
                    isinstance(kind, str)
                    and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", kind.strip())
                )
            )
            and lifecycle in {"invocation", "phase"}
            and visibility in {"show", "hide"}
        ):
            return None
        return cls(
            active_title=active.strip(),
            completed_title=completed.strip(),
            category=category,
            icon_key=icon_key.strip(),
            integration_key=(
                integration_key.strip() if isinstance(integration_key, str) else None
            ),
            kind=kind.strip() if isinstance(kind, str) else None,
            lifecycle=lifecycle,
            visibility=visibility,
        )


@dataclass(frozen=True)
class Capability:
    """One typed verb; the source of truth the doors (05) and agent (07) read."""

    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    executor: Executor
    billing_unit: BillingUnit | None
    docs_url: str | None = None
    activity: ActivityDescriptor | None = None
