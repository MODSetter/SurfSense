from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

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


class DestinationWrite(BaseModel):
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
    "/{destination}", response_model=DestinationRead, summary="Allow or refuse one"
)
def write_destination(
    destination: str, payload: DestinationWrite, session: SessionDep
) -> DestinationRead:
    if not is_destination(destination):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown egress destination"
        )
    return _read(set_enabled(session, destination, payload.enabled))
