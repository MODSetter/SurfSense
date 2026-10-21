from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import SessionDep
from modules.egress.models import EgressDestination
from modules.egress.service import (
    host_of,
    is_destination,
    list_destinations,
    set_enabled,
)

router = APIRouter(prefix="/egress", tags=["egress"])


class DestinationRead(BaseModel):
    destination: str
    host: str
    enabled: bool
    last_call_at: datetime | None


class DestinationsWrite(BaseModel):
    """Every destination one answer covers: one question can name several hosts."""

    destinations: list[str] = Field(min_length=1)
    enabled: bool


def _read(row: EgressDestination) -> DestinationRead:
    return DestinationRead(
        destination=row.destination,
        host=host_of(row.destination),
        enabled=row.enabled,
        last_call_at=row.last_call_at,
    )


@router.get("", response_model=list[DestinationRead], summary="List destinations")
def read_destinations(session: SessionDep) -> list[DestinationRead]:
    return [_read(row) for row in list_destinations(session)]


@router.put(
    "", response_model=list[DestinationRead], summary="Allow or refuse destinations"
)
def write_destinations(
    payload: DestinationsWrite, session: SessionDep
) -> list[DestinationRead]:
    """All or nothing: every destination is checked before any is written, and the
    request's one transaction commits them together, so a failed answer allows none.
    """
    unknown = [d for d in payload.destinations if not is_destination(d)]
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown egress destination: {', '.join(unknown)}",
        )
    return [
        _read(set_enabled(session, destination, payload.enabled))
        for destination in dict.fromkeys(payload.destinations)
    ]
