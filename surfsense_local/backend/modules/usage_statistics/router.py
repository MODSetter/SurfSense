from datetime import UTC, datetime

from fastapi import APIRouter

from api.dependencies import SessionDep
from modules.usage_statistics.activity_counts import read_counts
from modules.usage_statistics.dependencies import MachineReadingsDep, TodayDep
from modules.usage_statistics.hardware import hardware_buckets
from modules.usage_statistics.schemas import UsageSummaryRead
from modules.usage_statistics.week_activity import week_activity

router = APIRouter(prefix="/usage-statistics", tags=["usage-statistics"])


@router.get(
    "/summary",
    response_model=UsageSummaryRead,
    summary="This install's usage since a time, in the weekly report's buckets",
)
def read_summary(
    since: datetime,
    session: SessionDep,
    machine: MachineReadingsDep,
    today: TodayDep,
    first_run: datetime | None = None,
) -> UsageSummaryRead:
    """Computed on each read and sent nowhere: Electron main decides whether to report it.

    `first_run` is Electron's firstRunAt: no day before it counts as a day used.
    A `def`, so the device probe the hardware needs runs off the loop.
    """
    since = since if since.tzinfo is not None else since.replace(tzinfo=UTC)
    if first_run is not None and first_run.tzinfo is None:
        first_run = first_run.replace(tzinfo=UTC)
    counts = read_counts()
    return UsageSummaryRead(
        week=week_activity(
            session,
            since,
            counts,
            machine.holds_local_model,
            today=today,
            first_run=None if first_run is None else first_run.astimezone(UTC).date(),
        ),
        hardware=hardware_buckets(
            machine.inventory(), machine.ram_total_bytes(), machine.os_adapter_names
        ),
        ui_language=machine.ui_language(),
    )
