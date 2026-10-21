import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from host.tests.serving import serving
from host.tests.stand_in_posthog import StandInPostHog
from host.usage_meter.call_counts import CallKey, Tally
from host.usage_meter.meter_settings import MeterSettings
from host.usage_meter.rollup import main
from host.usage_meter.usage_meter import UsageMeter
from host.usage_meter.usage_store import UsageStore

# plugins/remote/, the import root `python -m` runs from.
IMPORT_ROOT = Path(__file__).resolve().parents[2]
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
    assert posthog.events == [
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
