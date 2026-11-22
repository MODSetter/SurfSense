"""Licensing is off in every release (ADR 0092); only the maintainer's override turns it on,
and with it off a job's access no longer depends on any licence."""

from types import SimpleNamespace

import pytest

from modules.jobs.packs.access import DEV_SWITCH, job_access
from modules.license import licensing
from modules.license.licensing import OVERRIDE, licensing_on
from tests.unit.jobs.test_job_access import _pack

pytestmark = pytest.mark.unit


def test_a_release_ships_with_licensing_off() -> None:
    """Compiled in: no setting a user could flip."""
    assert licensing.LICENSING_ON is False


@pytest.mark.parametrize(("value", "on"), [(None, False), ("0", False), ("1", True)])
def test_only_the_override_turns_it_on(
    monkeypatch: pytest.MonkeyPatch, value: str | None, on: bool
) -> None:
    """Exactly `1`, as the tests' conftest sets it."""
    if value is None:
        monkeypatch.delenv(OVERRIDE, raising=False)
    else:
        monkeypatch.setenv(OVERRIDE, value)

    assert licensing_on() is on


@pytest.mark.parametrize("state", ["none", "license_expired", "clock_untrusted"])
def test_with_licensing_off_a_paid_job_runs_whatever_the_licence(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """No licence, one that ended, or a clock behind one: none of them locks a job."""
    monkeypatch.delenv(OVERRIDE, raising=False)
    monkeypatch.delenv(DEV_SWITCH, raising=False)
    monkeypatch.setattr(
        "modules.jobs.packs.access.status",
        lambda _session: SimpleNamespace(state=state, plan="business", jobs=None),
    )

    access = job_access(None, *_pack())

    assert access.allowed and access.code is None
