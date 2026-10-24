import json
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from host.app import host_app
from host.tests.serving import serving
from host.tests.stand_in_posthog import StandInPostHog
from host.usage_meter.call_counts import CallKey, Tally
from host.usage_meter.meter_settings import MeterSettings
from host.usage_meter.rollup import main
from host.usage_meter.usage_meter import UsageMeter
from host.usage_meter.usage_store import UsageStore

# backend/plugins/, where `python -m host...` imports from.
IMPORT_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = Path(__file__).parent / "sample_plugins"
TODAY = "2026-10-21"
YESTERDAY = "2026-10-20"


def at_noon(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T12:00:00+00:00")


def meter_from_env(env: dict[str, str]) -> UsageMeter:
    return UsageMeter.from_settings(
        MeterSettings.from_env(env), clock=lambda: at_noon(TODAY)
    )


def record_yesterday(meter: UsageMeter) -> None:
    meter.record(CallKey("2026-10-19", "lic-b", "notes", "search", "ok"), 10)
    meter.record(CallKey(YESTERDAY, "lic-a", "notes", "search", "ok"), 100)
    meter.record(CallKey(YESTERDAY, "lic-a", "notes", "search", "ok"), 50)
    meter.record(CallKey(YESTERDAY, "lic-b", "notes", "search", "ok"), 10)
    meter.record(CallKey(YESTERDAY, "unlicensed", "notes", "search", "refused"), 5)


def happens(condition: Callable[[], bool], seconds: float = 5) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("it did not happen in time")
        time.sleep(0.02)


def without_id(event: dict) -> dict:
    """An event less its uuid, which test_a_day_sent_again_carries_the_same_event_ids checks."""
    return {field: value for field, value in event.items() if field != "uuid"}


def personless(name: str, properties: dict) -> dict:
    return {
        "event": name,
        "distinct_id": "surfsense-plugin-host",
        "timestamp": f"{YESTERDAY}T12:00:00Z",
        "properties": {
            "day": YESTERDAY,
            **properties,
            "$process_person_profile": False,
            "$geoip_disable": True,
        },
    }


async def test_yesterday_s_totals_go_to_posthog_once_with_no_license_id(
    tmp_path: Path,
) -> None:
    posthog = StandInPostHog()
    with serving(posthog.app) as url:
        meter = meter_from_env(
            {
                "USAGE_DB_PATH": str(tmp_path / "usage.sqlite3"),
                "POSTHOG_API_KEY": "phc_test",
                "POSTHOG_HOST": url,
            }
        )
        record_yesterday(meter)
        await meter.run_daily_jobs()
        await meter.run_daily_jobs()

    assert len(posthog.bodies) == 1
    assert b'"api_key":"phc_test"' in posthog.bodies[0].replace(b" ", b"")
    assert [without_id(event) for event in posthog.events] == [
        personless(
            "plugin_usage_daily",
            {
                "plugin": "notes",
                "tool": "search",
                "outcome": "ok",
                "calls": 3,
                "total_ms": 160,
                "distinct_licences": 2,
            },
        ),
        personless(
            "plugin_usage_daily",
            {
                "plugin": "notes",
                "tool": "search",
                "outcome": "refused",
                "calls": 1,
                "total_ms": 5,
                "distinct_licences": 0,
            },
        ),
        personless("plugin_licences_daily", {"active_licences": 2, "new_licences": 1}),
    ]
    assert b"lic-a" not in posthog.bodies[0]
    assert b"lic-b" not in posthog.bodies[0]


def test_the_serving_host_sends_yesterday_s_rollup_and_retries_until_it_is_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At startup, then every DAILY_JOBS_SECONDS (made short here) until PostHog takes it."""
    monkeypatch.setattr("host.usage_meter.usage_meter.DAILY_JOBS_SECONDS", 0.05)
    posthog = StandInPostHog()
    posthog.failing = True
    with serving(posthog.app) as url:
        meter = meter_from_env(
            {
                "USAGE_DB_PATH": str(tmp_path / "usage.sqlite3"),
                "POSTHOG_API_KEY": "phc_test",
                "POSTHOG_HOST": url,
            }
        )
        record_yesterday(meter)
        with serving(host_app(SAMPLES, meter=meter)):
            happens(lambda: len(posthog.bodies) >= 2)
            posthog.failing = False
            happens(lambda: bool(posthog.taken))
            # A few more runs, which find the day already sent.
            time.sleep(0.3)

    assert len(posthog.taken) == 1
    assert b"lic-a" not in posthog.taken[0]
    assert [event["event"] for event in json.loads(posthog.taken[0])["batch"]] == [
        "plugin_usage_daily",
        "plugin_usage_daily",
        "plugin_licences_daily",
    ]


async def test_nothing_is_sent_without_a_posthog_key(tmp_path: Path) -> None:
    posthog = StandInPostHog()
    with serving(posthog.app) as url:
        meter = meter_from_env(
            {"USAGE_DB_PATH": str(tmp_path / "usage.sqlite3"), "POSTHOG_HOST": url}
        )
        record_yesterday(meter)
        await meter.run_daily_jobs()

    assert posthog.bodies == []


async def test_a_rollup_posthog_refused_is_sent_on_a_later_run(tmp_path: Path) -> None:
    posthog = StandInPostHog()
    posthog.failing = True
    with serving(posthog.app) as url:
        meter = meter_from_env(
            {
                "USAGE_DB_PATH": str(tmp_path / "usage.sqlite3"),
                "POSTHOG_API_KEY": "phc_test",
                "POSTHOG_HOST": url,
            }
        )
        record_yesterday(meter)
        await meter.run_daily_jobs()
        posthog.failing = False
        await meter.run_daily_jobs()

    assert len(posthog.bodies) == 2
    assert [event["event"] for event in posthog.events[-3:]] == [
        "plugin_usage_daily",
        "plugin_usage_daily",
        "plugin_licences_daily",
    ]


def test_the_meter_s_settings_default_to_a_file_under_the_working_directory() -> None:
    assert MeterSettings.from_env({}) == MeterSettings(
        Path("usage/plugin-usage.sqlite3"), None, None, "https://us.i.posthog.com"
    )


def test_the_rollup_command_sends_the_day_it_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "usage.sqlite3"
    UsageStore(path).add(
        {CallKey(YESTERDAY, "lic-a", "notes", "search", "ok"): Tally(2, 40)}
    )
    posthog = StandInPostHog()
    with serving(posthog.app) as url:
        monkeypatch.setenv("USAGE_DB_PATH", str(path))
        monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
        monkeypatch.setenv("POSTHOG_HOST", url)
        assert main(["--day", YESTERDAY]) == 0

    assert [event["event"] for event in posthog.events] == [
        "plugin_usage_daily",
        "plugin_licences_daily",
    ]
    assert b"lic-a" not in posthog.bodies[0]


def test_a_day_sent_again_carries_the_same_event_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So PostHog keeps one copy of a day sent twice instead of counting it again."""
    path = tmp_path / "usage.sqlite3"
    UsageStore(path).add(
        {
            CallKey("2026-10-19", "lic-a", "notes", "search", "ok"): Tally(1, 10),
            CallKey(YESTERDAY, "lic-a", "notes", "search", "ok"): Tally(2, 40),
            CallKey(YESTERDAY, "lic-a", "notes", "search", "refused"): Tally(1, 5),
        }
    )
    posthog = StandInPostHog()
    with serving(posthog.app) as url:
        monkeypatch.setenv("USAGE_DB_PATH", str(path))
        monkeypatch.setenv("POSTHOG_API_KEY", "phc_test")
        monkeypatch.setenv("POSTHOG_HOST", url)
        for day in (YESTERDAY, YESTERDAY, "2026-10-19"):
            assert main(["--day", day]) == 0

    first, again, other_day = (
        [event["uuid"] for event in json.loads(body)["batch"]]
        for body in posthog.bodies
    )
    assert first == again
    assert len(set(first)) == len(first) == 3
    assert not set(other_day) & set(first)


@pytest.mark.parametrize(
    ("day", "key"), [("2026-10-20", None), ("20-10-2026", "phc_test")]
)
def test_the_rollup_command_needs_a_key_and_a_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, day: str, key: str | None
) -> None:
    path = tmp_path / "usage.sqlite3"
    UsageStore(path).add({})
    monkeypatch.setenv("USAGE_DB_PATH", str(path))
    if key:
        monkeypatch.setenv("POSTHOG_API_KEY", key)
    else:
        monkeypatch.delenv("POSTHOG_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exited:
        main(["--day", day])
    assert exited.value.code == 2


def test_the_rollup_command_runs_as_a_module() -> None:
    ran = subprocess.run(
        [sys.executable, "-m", "host.usage_meter.rollup", "--help"],
        cwd=IMPORT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert ran.returncode == 0, ran.stderr
    assert "--day" in ran.stdout
    assert ran.stderr == ""
