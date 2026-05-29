"""Lock the ``ScheduleTriggerParams`` validation contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.automations.triggers.builtin.schedule.params import ScheduleTriggerParams

pytestmark = pytest.mark.unit


def test_schedule_params_accept_valid_cron_and_iana_timezone() -> None:
    """A well-formed cron + IANA timezone yields a populated model.
    Locks the round-trip path users go through when creating a trigger."""
    params = ScheduleTriggerParams(cron="0 9 * * 1-5", timezone="Africa/Kigali")

    assert params.cron == "0 9 * * 1-5"
    assert params.timezone == "Africa/Kigali"


def test_schedule_params_reject_malformed_cron_with_validation_error() -> None:
    """``InvalidCronError`` from ``validate_cron`` must surface as
    Pydantic ``ValidationError`` so the FastAPI layer returns 422 instead
    of letting the bad value reach storage."""
    with pytest.raises(ValidationError):
        ScheduleTriggerParams(cron="not cron", timezone="UTC")


def test_schedule_params_reject_unknown_timezone_with_validation_error() -> None:
    """An unknown timezone is rejected at the API boundary — same gate
    as the cron expression itself."""
    with pytest.raises(ValidationError):
        ScheduleTriggerParams(cron="0 9 * * *", timezone="Mars/Olympus_Mons")
