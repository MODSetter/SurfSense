from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from app.gateway import byo_long_poll, runner


class ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self._rows)


class SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest_asyncio.fixture(autouse=True)
async def cleanup_supervisors():
    yield
    await byo_long_poll.stop_byo_long_poll_supervisors()


@pytest.mark.asyncio
async def test_start_byo_long_poll_noops_when_mode_is_webhook(monkeypatch):
    monkeypatch.setattr(byo_long_poll.config, "GATEWAY_ENABLED", True)
    monkeypatch.setattr(byo_long_poll.config, "GATEWAY_TELEGRAM_INTAKE_MODE", "webhook")
    monkeypatch.setattr(
        byo_long_poll.config, "GATEWAY_WHATSAPP_INTAKE_MODE", "disabled"
    )

    await byo_long_poll.start_byo_long_poll_supervisors()

    assert byo_long_poll._tasks == set()


@pytest.mark.asyncio
async def test_start_byo_long_poll_noops_when_no_byo_accounts(mocker, monkeypatch):
    monkeypatch.setattr(byo_long_poll.config, "GATEWAY_ENABLED", True)
    monkeypatch.setattr(
        byo_long_poll.config, "GATEWAY_TELEGRAM_INTAKE_MODE", "longpoll"
    )
    monkeypatch.setattr(
        byo_long_poll.config, "GATEWAY_WHATSAPP_INTAKE_MODE", "disabled"
    )
    session = mocker.AsyncMock()
    session.execute.return_value = ScalarResult([])
    monkeypatch.setattr(
        byo_long_poll,
        "async_session_maker",
        lambda: SessionContext(session),
    )

    await byo_long_poll.start_byo_long_poll_supervisors()

    assert byo_long_poll._tasks == set()


@pytest.mark.asyncio
async def test_start_byo_long_poll_spawns_one_supervisor_per_account(
    mocker, monkeypatch
):
    monkeypatch.setattr(byo_long_poll.config, "GATEWAY_ENABLED", True)
    monkeypatch.setattr(
        byo_long_poll.config, "GATEWAY_TELEGRAM_INTAKE_MODE", "longpoll"
    )
    monkeypatch.setattr(
        byo_long_poll.config, "GATEWAY_WHATSAPP_INTAKE_MODE", "disabled"
    )
    accounts = [mocker.Mock(id=1), mocker.Mock(id=2)]
    session = mocker.AsyncMock()
    session.execute.return_value = ScalarResult(accounts)
    monkeypatch.setattr(
        byo_long_poll,
        "async_session_maker",
        lambda: SessionContext(session),
    )
    monkeypatch.setattr(
        byo_long_poll, "account_token", lambda account: f"token-{account.id}"
    )

    async def forever(_account_id: int, _token: str) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(byo_long_poll, "_byo_account_supervisor", forever)

    await byo_long_poll.start_byo_long_poll_supervisors()

    assert len(byo_long_poll._tasks) == 2


@pytest.mark.asyncio
async def test_supervisor_retries_after_run_returns(mocker, monkeypatch):
    byo_long_poll._shutdown_event = asyncio.Event()
    run = mocker.AsyncMock(side_effect=[None, None])
    monkeypatch.setattr(byo_long_poll, "_run_telegram_account", run)
    sleep_count = 0

    async def fake_sleep(_seconds: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            assert byo_long_poll._shutdown_event is not None
            byo_long_poll._shutdown_event.set()

    monkeypatch.setattr(byo_long_poll, "_sleep_or_shutdown", fake_sleep)

    await byo_long_poll._byo_account_supervisor(7, "token")

    assert run.await_count == 2


@pytest.mark.asyncio
async def test_shutdown_cancels_running_supervisors(mocker, monkeypatch):
    monkeypatch.setattr(byo_long_poll.config, "GATEWAY_ENABLED", True)
    monkeypatch.setattr(
        byo_long_poll.config, "GATEWAY_TELEGRAM_INTAKE_MODE", "longpoll"
    )
    monkeypatch.setattr(
        byo_long_poll.config, "GATEWAY_WHATSAPP_INTAKE_MODE", "disabled"
    )
    session = mocker.AsyncMock()
    session.execute.return_value = ScalarResult([mocker.Mock(id=1)])
    monkeypatch.setattr(
        byo_long_poll,
        "async_session_maker",
        lambda: SessionContext(session),
    )
    monkeypatch.setattr(byo_long_poll, "account_token", lambda _account: "token")

    async def forever(_account_id: int, _token: str) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(byo_long_poll, "_byo_account_supervisor", forever)

    await byo_long_poll.start_byo_long_poll_supervisors()
    await byo_long_poll.stop_byo_long_poll_supervisors()

    assert byo_long_poll._tasks == set()


@pytest.mark.asyncio
async def test_run_telegram_account_persists_for_fastapi_inbox_worker(
    mocker, monkeypatch
):
    class ConnectionContext:
        async def __aenter__(self):
            conn = mocker.AsyncMock()
            conn.scalar.return_value = True
            return conn

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class EngineStub:
        def connect(self):
            return ConnectionContext()

    class AdapterStub:
        def __init__(self, _token: str) -> None:
            pass

        async def fetch_updates(self, *, offset: int | None):
            yield {"update_id": 11, "message": {"message_id": 5}}

        def parse_inbound(self, update):
            return mocker.Mock(external_message_id="5", event_kind="message")

    first_session = mocker.AsyncMock()
    first_session.get.return_value = mocker.Mock(cursor_state={})
    second_session = mocker.AsyncMock()
    contexts = iter([SessionContext(first_session), SessionContext(second_session)])
    monkeypatch.setattr(runner, "engine", EngineStub())
    monkeypatch.setattr(runner, "async_session_maker", lambda: next(contexts))
    monkeypatch.setattr(runner, "TelegramAdapter", AdapterStub)
    persist = mocker.AsyncMock(return_value=42)
    monkeypatch.setattr(runner, "persist_inbound_event", persist)

    await runner._run_telegram_account(123, "token")

    second_session.commit.assert_awaited_once()
    persist.assert_awaited_once()
    assert persist.await_args.kwargs["request_id"].startswith("gateway_")
