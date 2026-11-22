import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

import anyio
import httpx2
import pytest

from host.app import host_app
from host.tests.mcp_calls import call, raw_request, tool_names
from host.tests.serving import serving
from host.usage_meter.call_counts import CallKey
from host.usage_meter.rollup import rollup_events
from host.usage_meter.usage_meter import UsageMeter
from host.usage_meter.usage_store import DailyUsage, UsageStore

SAMPLES = Path(__file__).parent / "sample_plugins"
DAY = "2026-10-21"
ADMIN = {"authorization": "Bearer admin-token"}

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "opencode", "version": "1.18.34"},
    },
}


def tool_call(tool: str, arguments: dict, request_id: int = 7) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }


def store_in(folder: Path) -> UsageStore:
    return UsageStore(folder / "usage" / "plugin-usage.sqlite3")


def meter_in(folder: Path) -> UsageMeter:
    return UsageMeter(
        store_in(folder),
        clock=lambda: datetime.fromisoformat(f"{DAY}T12:00:00+00:00"),
    )


def written_under(folder: Path) -> bytes:
    """Every byte the meter wrote, its write-ahead log included."""
    return b"".join(path.read_bytes() for path in folder.iterdir())


def counted(usage: DailyUsage) -> set[tuple[str, str, str, int, int]]:
    return {
        (t.plugin, t.tool, t.outcome, t.calls, t.distinct_licences) for t in usage.tools
    }


def in_the_file(folder: Path) -> set[tuple[str, str, str, int, int]]:
    """The day's counts read from a store of its own: the meter's reads write first."""
    return counted(store_in(folder).daily_usage(DAY))


async def test_each_tool_call_is_counted_by_plugin_tool_and_outcome(
    tmp_path: Path,
) -> None:
    """A tool's MCP error is `tool_error`; a name the plugin lacks is kept as `unknown`."""
    meter = meter_in(tmp_path)
    with serving(host_app(SAMPLES, meter=meter)) as base:
        await call(f"{base}/notes/mcp", "search", {"query": "a"})
        await call(f"{base}/notes/mcp", "search", {"query": "b"})
        await call(f"{base}/failing/mcp", "explode", {})
        raw_request(f"{base}/notes/mcp", tool_call("delete-everything", {}))

    usage = await meter.daily_usage(DAY)
    assert counted(usage) == {
        ("notes", "search", "ok", 2, 0),
        ("failing", "explode", "tool_error", 1, 0),
        ("notes", "unknown", "tool_error", 1, 0),
    }
    assert all(t.total_ms >= 0 for t in usage.tools)


def test_the_counts_are_written_when_the_host_stops(tmp_path: Path) -> None:
    meter = meter_in(tmp_path)
    with serving(host_app(SAMPLES, meter=meter)) as base:
        raw_request(f"{base}/notes/mcp", tool_call("search", {"query": "a"}))

    assert in_the_file(tmp_path) == {("notes", "search", "ok", 1, 0)}


def test_the_counts_are_written_while_the_host_serves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every FLUSH_SECONDS, made short here."""
    monkeypatch.setattr("host.usage_meter.usage_meter.FLUSH_SECONDS", 0.05)
    meter = meter_in(tmp_path)
    with serving(host_app(SAMPLES, meter=meter)) as base:
        raw_request(f"{base}/notes/mcp", tool_call("search", {"query": "a"}))
        deadline = time.monotonic() + 5
        while not in_the_file(tmp_path) and time.monotonic() < deadline:
            time.sleep(0.05)
        written = in_the_file(tmp_path)

    assert written == {("notes", "search", "ok", 1, 0)}


async def test_only_tool_calls_are_counted(tmp_path: Path) -> None:
    meter = meter_in(tmp_path)
    with serving(host_app(SAMPLES, meter=meter)) as base:
        raw_request(f"{base}/notes/mcp", INITIALIZE)
        assert await tool_names(f"{base}/notes/mcp") == ["search"]
        assert httpx2.get(f"{base}/notes/mcp").status_code == 405
        assert httpx2.get(f"{base}/health").status_code == 200

    assert (await meter.daily_usage(DAY)).tools == []


def test_a_stopped_call_is_counted_as_cancelled(tmp_path: Path) -> None:
    meter = meter_in(tmp_path)
    mark = tmp_path / "mark"
    thread = {"authorization": "License k-1", "x-surfsense-calls": "t-1"}
    with serving(host_app(SAMPLES, meter=meter)) as base:
        sender = threading.Thread(
            target=raw_request,
            args=(f"{base}/slow/mcp", tool_call("wait", {"mark": str(mark)}), thread),
        )
        sender.start()
        deadline = time.monotonic() + 5
        while not mark.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert httpx2.post(f"{base}/cancel", headers=thread).status_code == 202
        sender.join(timeout=10)

    usage = anyio.run(meter.daily_usage, DAY)
    assert counted(usage) == {("slow", "wait", "cancelled", 1, 0)}


async def test_what_a_call_carries_never_reaches_the_meter_s_file_or_rollup(
    tmp_path: Path,
) -> None:
    """Its arguments, its key and its thread's token: only the tool's name is kept."""
    secrets = ["canary-query-4d1c", "canary-key-8be0", "canary-thread-0a7f"]
    query, key, thread = secrets
    headers = {"authorization": f"License {key}", "x-surfsense-calls": thread}
    meter = meter_in(tmp_path)
    with serving(
        host_app(SAMPLES, meter=meter, usage_admin_token="admin-token")
    ) as base:
        found = await call(f"{base}/notes/mcp", "search", {"query": query}, headers)
        daily = httpx2.get(
            f"{base}/admin/usage/daily", params={"day": DAY}, headers=ADMIN
        )

    usage = await meter.daily_usage(DAY)
    written = written_under(tmp_path / "usage")
    sent = json.dumps(rollup_events(usage))
    assert found.structured_content == {"result": f"found {query}"}
    assert counted(usage) == {("notes", "search", "ok", 1, 0)}
    assert b"search" in written
    for secret in secrets:
        assert secret.encode() not in written
        assert secret not in sent
        assert secret not in daily.text


def test_a_body_too_long_to_read_first_reaches_the_plugin_whole_and_uncounted(
    tmp_path: Path,
) -> None:
    """Before the license check the meter reads at most 1 MiB, so no caller can make
    the host hold more."""
    meter = meter_in(tmp_path)
    query = "q" * (2 * 1024 * 1024)
    with serving(host_app(SAMPLES, meter=meter)) as base:
        answer = raw_request(f"{base}/notes/mcp", tool_call("search", {"query": query}))

    assert answer.status_code == 200
    assert f"found {query}" in answer.text
    assert anyio.run(meter.daily_usage, DAY).tools == []


async def test_a_meter_that_raises_never_fails_the_call(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Its failure is logged once, however many calls it fails on."""
    meter = meter_in(tmp_path)

    def broken(key: CallKey, ms: int) -> None:
        raise RuntimeError("the meter broke")

    meter.record = broken  # type: ignore[method-assign]
    with (
        caplog.at_level(logging.ERROR),
        serving(host_app(SAMPLES, meter=meter)) as base,
    ):
        first = await call(f"{base}/notes/mcp", "search", {"query": "a"})
        second = await call(f"{base}/notes/mcp", "search", {"query": "b"})

    assert first.structured_content == {"result": "found a"}
    assert second.structured_content == {"result": "found b"}
    logged = [r for r in caplog.records if "counting a call" in r.getMessage()]
    assert len(logged) == 1


async def test_counts_the_store_could_not_take_wait_for_the_next_write(
    tmp_path: Path,
) -> None:
    """A store that cannot be written loses nothing and fails no call."""
    blocker = tmp_path / "usage"
    blocker.write_text("a file where the meter's folder should be")
    meter = meter_in(tmp_path)
    with serving(host_app(SAMPLES, meter=meter)) as base:
        found = await call(f"{base}/notes/mcp", "search", {"query": "a"})

    blocker.unlink()
    await meter.flush()

    assert found.structured_content == {"result": "found a"}
    assert counted(await meter.daily_usage(DAY)) == {("notes", "search", "ok", 1, 0)}


def test_the_usage_records_are_not_served_without_an_admin_token(
    tmp_path: Path,
) -> None:
    with serving(host_app(SAMPLES, meter=meter_in(tmp_path))) as base:
        first_seen = httpx2.get(f"{base}/admin/usage/first-seen", headers=ADMIN)
        daily = httpx2.get(f"{base}/admin/usage/daily?day={DAY}", headers=ADMIN)

    assert (first_seen.status_code, daily.status_code) == (404, 404)


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer wrong-token", "admin-token", "Basic admin-token", "Bearer"],
)
def test_the_usage_records_need_the_admin_token(
    tmp_path: Path, authorization: str | None
) -> None:
    headers = {"authorization": authorization} if authorization else {}
    meter = meter_in(tmp_path)
    with serving(
        host_app(SAMPLES, meter=meter, usage_admin_token="admin-token")
    ) as base:
        first_seen = httpx2.get(f"{base}/admin/usage/first-seen", headers=headers)
        daily = httpx2.get(f"{base}/admin/usage/daily?day={DAY}", headers=headers)

    assert (first_seen.status_code, daily.status_code) == (401, 401)
    assert first_seen.json() == {"reason": "unauthorized"}


def test_the_admin_token_reads_first_days_and_a_day_s_totals(tmp_path: Path) -> None:
    """The daily totals name no license, only how many there were."""
    meter = meter_in(tmp_path)
    meter.record(CallKey("2026-10-20", "lic-b", "notes", "search", "ok"), 20)
    meter.record(CallKey(DAY, "lic-a", "notes", "search", "ok"), 30)
    meter.record(CallKey(DAY, "lic-b", "notes", "search", "ok"), 10)
    with serving(
        host_app(SAMPLES, meter=meter, usage_admin_token="admin-token")
    ) as base:
        first_seen = httpx2.get(f"{base}/admin/usage/first-seen", headers=ADMIN)
        daily = httpx2.get(
            f"{base}/admin/usage/daily", params={"day": DAY}, headers=ADMIN
        )
        no_day = httpx2.get(f"{base}/admin/usage/daily", headers=ADMIN)
        bad_day = httpx2.get(
            f"{base}/admin/usage/daily", params={"day": "21/10/2026"}, headers=ADMIN
        )

    assert first_seen.json() == {"licences": {"lic-a": DAY, "lic-b": "2026-10-20"}}
    assert daily.json() == {
        "day": DAY,
        "tools": [
            {
                "plugin": "notes",
                "tool": "search",
                "outcome": "ok",
                "calls": 2,
                "total_ms": 40,
                "distinct_licences": 2,
            }
        ],
        "active_licences": 2,
        "new_licences": 1,
    }
    assert (no_day.status_code, bad_day.status_code) == (400, 400)
    assert bad_day.json() == {"reason": "invalid_day"}


async def test_rows_older_than_thirteen_months_are_forgotten(tmp_path: Path) -> None:
    """A license's first day is kept while it has any row left."""
    meter = meter_in(tmp_path)
    meter.record(CallKey("2025-09-20", "lic-gone", "notes", "search", "ok"), 1)
    meter.record(CallKey("2025-09-20", "lic-kept", "notes", "search", "ok"), 1)
    meter.record(CallKey("2025-09-21", "lic-kept", "notes", "search", "ok"), 1)

    await meter.run_daily_jobs()

    assert await meter.first_seen() == {"lic-kept": "2025-09-20"}
    assert (await meter.daily_usage("2025-09-20")).tools == []
    assert counted(await meter.daily_usage("2025-09-21")) == {
        ("notes", "search", "ok", 1, 1)
    }
