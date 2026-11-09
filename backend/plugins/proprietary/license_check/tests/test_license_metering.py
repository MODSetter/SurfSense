"""The host's usage meter behind the real license check: calls counted under Keygen's license id."""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import httpx2
import pytest

from host.app import host_app
from host.tests.mcp_calls import call, raw_request, tool_names
from host.tests.serving import serving
from host.usage_meter.rollup import rollup_events
from host.usage_meter.usage_meter import UsageMeter
from host.usage_meter.usage_store import UsageStore
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
    license_id_of,
)

SAMPLES = Path(__file__).parent / "sample_plugins"
DAY = "2026-10-21"
ADMIN = {"authorization": "Bearer admin-token"}


def scrape(url: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "scrape", "arguments": {"url": url}},
    }


def written_under(folder: Path) -> bytes:
    """Every byte the meter wrote, its write-ahead log included."""
    return b"".join(path.read_bytes() for path in folder.iterdir())


def meter_in(folder: Path) -> UsageMeter:
    return UsageMeter(
        UsageStore(folder / "plugin-usage.sqlite3"),
        clock=lambda: datetime.fromisoformat(f"{DAY}T12:00:00+00:00"),
    )


@pytest.fixture
def keygen(monkeypatch: pytest.MonkeyPatch) -> Iterator[StandInKeygen]:
    stand_in = StandInKeygen({})
    with serving(stand_in.app) as url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        monkeypatch.delenv("KEYGEN_HOST", raising=False)
        yield stand_in


async def test_calls_are_counted_under_the_license_keygen_names(
    tmp_path: Path, keygen: StandInKeygen
) -> None:
    """A refused call counts under its license when Keygen knows the key, else unlicensed."""
    keygen.codes.update({"k-1": "VALID", "k-2": "EXPIRED"})
    meter = meter_in(tmp_path)
    with serving(
        host_app(SAMPLES, meter=meter, usage_admin_token="admin-token")
    ) as base:
        paid = f"{base}/paid/mcp"
        licensed = {"authorization": "License k-1"}
        scraped = await call(paid, "scrape", {"url": "https://a.example"}, licensed)
        await tool_names(paid, licensed)
        httpx2.get(f"{base}/license", headers=licensed)
        expired = raw_request(paid, scrape("x"), {"authorization": "License k-2"})
        missing = raw_request(paid, scrape("x"))
        unknown = raw_request(
            f"{base}/paid-too/mcp", scrape("x"), {"authorization": "License k-3"}
        )
        first_seen = httpx2.get(f"{base}/admin/usage/first-seen", headers=ADMIN)
        daily = httpx2.get(
            f"{base}/admin/usage/daily", params={"day": DAY}, headers=ADMIN
        )

    assert not scraped.is_error
    assert (expired.status_code, missing.status_code, unknown.status_code) == (
        403,
        401,
        403,
    )
    assert first_seen.json() == {
        "licences": {license_id_of("k-1"): DAY, license_id_of("k-2"): DAY}
    }
    assert [
        (t["plugin"], t["tool"], t["outcome"], t["calls"], t["distinct_licences"])
        for t in daily.json()["tools"]
    ] == [
        ("paid", "scrape", "ok", 1, 1),
        ("paid", "scrape", "refused", 2, 1),
        ("paid-too", "scrape", "refused", 1, 0),
    ]
    assert (daily.json()["active_licences"], daily.json()["new_licences"]) == (2, 2)
    # The license ids stay on the host: the daily totals only count them.
    assert license_id_of("k-1") not in daily.text


async def test_neither_the_key_nor_the_thread_s_token_nor_the_arguments_are_kept(
    tmp_path: Path, keygen: StandInKeygen
) -> None:
    key, thread, asked = (
        "canary-key-31d9",
        "canary-thread-c04e",
        "https://canary-asked-77b2.example",
    )
    keygen.codes[key] = "VALID"
    meter = meter_in(tmp_path)
    headers = {"authorization": f"License {key}", "x-surfsense-calls": thread}
    with serving(host_app(SAMPLES, meter=meter)) as base:
        scraped = await call(f"{base}/paid/mcp", "scrape", {"url": asked}, headers)

    usage = await meter.daily_usage(DAY)
    written = written_under(tmp_path)
    sent = json.dumps(rollup_events(usage))
    assert scraped.structured_content == {"result": f"scraped {asked}"}
    assert license_id_of(key).encode() in written
    assert license_id_of(key) not in sent
    for secret in (key, thread, asked):
        assert secret.encode() not in written
        assert secret not in sent
