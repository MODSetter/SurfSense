from __future__ import annotations

import asyncio

import pytest

from app.gateway import inbox_worker


@pytest.mark.asyncio
async def test_inbox_worker_claims_and_processes_in_fastapi_process(
    mocker, monkeypatch
):
    claim = mocker.AsyncMock(return_value=7)
    process = mocker.AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(inbox_worker, "claim_next_inbound_event", claim)
    monkeypatch.setattr(inbox_worker, "process_inbound_event", process)

    with pytest.raises(asyncio.CancelledError):
        await inbox_worker._process_inbox_forever()

    claim.assert_awaited_once()
    process.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_start_stop_gateway_inbox_worker(mocker, monkeypatch):
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def run_forever():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(inbox_worker, "_process_inbox_forever", run_forever)
    inbox_worker._task = None

    await inbox_worker.start_gateway_inbox_worker()
    await asyncio.wait_for(started.wait(), timeout=1)
    await inbox_worker.stop_gateway_inbox_worker()

    assert stopped.is_set()
    assert inbox_worker._task is None
