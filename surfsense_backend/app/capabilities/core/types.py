"""``Capability`` registry contracts shared by every verb."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pydantic import BaseModel
    from sqlalchemy.ext.asyncio import AsyncSession


class BillingUnit(StrEnum):
    """The meter a verb charges on (priced by the billing service, 03c). ``None`` = free."""

    WEB_CRAWL = "web_crawl"


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


@dataclass(frozen=True)
class Capability:
    """One typed verb; the source of truth the doors (05) and agent (07) read."""

    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    executor: Executor
    billing_unit: BillingUnit | None
