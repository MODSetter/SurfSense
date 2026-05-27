from __future__ import annotations

import inspect

import pytest

from app.db import ExternalChatPlatform, ExternalChatAccount
from app.routes import gateway_webhook_routes as routes


class RequestStub:
    def __init__(self, payload=None, *, headers=None, json_exc: Exception | None = None):
        self.headers = headers or {}
        self._payload = payload
        self._json_exc = json_exc

    async def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._payload


def _account(secret: str = "secret") -> ExternalChatAccount:
    return ExternalChatAccount(
        id=123,
        platform=ExternalChatPlatform.TELEGRAM,
        webhook_secret=secret,
        bot_username="surf_bot",
    )


async def _call_webhook(*, request: RequestStub, account_id: int, session):
    return await routes.telegram_webhook(
        request=request,
        account_id=account_id,
        session=session,
    )


@pytest.mark.asyncio
async def test_telegram_webhook_returns_200_on_null_update_id(mocker):
    session = mocker.AsyncMock()
    session.get.return_value = _account()
    request = RequestStub(
        {"message": {"message_id": 7}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )

    response = await _call_webhook(
        request=request,
        account_id=123,
        session=session,
    )

    assert response.status_code == 200
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_webhook_returns_200_on_bad_json(mocker, monkeypatch):
    parse_metric = mocker.Mock()
    monkeypatch.setattr(routes, "record_gateway_webhook_parse_error", parse_metric)
    request = RequestStub(json_exc=ValueError("bad json"))

    response = await _call_webhook(
        request=request,
        account_id=123,
        session=mocker.AsyncMock(),
    )

    assert response.status_code == 200
    parse_metric.assert_called_once_with()


@pytest.mark.asyncio
async def test_resolve_webhook_account_rejects_missing_or_wrong_header(mocker):
    session = mocker.AsyncMock()
    session.get.return_value = _account()

    with pytest.raises(routes.HTTPException) as missing:
        await routes._resolve_webhook_account(
            session,
            account_id=123,
            header_secret=None,
        )
    assert missing.value.status_code == 403

    with pytest.raises(routes.HTTPException) as wrong:
        await routes._resolve_webhook_account(
            session,
            account_id=123,
            header_secret="wrong",
        )
    assert wrong.value.status_code == 403


@pytest.mark.asyncio
async def test_telegram_webhook_persists_for_fastapi_inbox_worker(mocker, monkeypatch):
    session = mocker.AsyncMock()
    session.get.return_value = _account()
    persist = mocker.AsyncMock(return_value=99)
    monkeypatch.setattr(routes, "persist_inbound_event", persist)

    request = RequestStub(
        {
            "update_id": 10,
            "message": {"message_id": 7, "chat": {"id": 1}, "from": {"id": 2}},
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )

    response = await _call_webhook(
        request=request,
        account_id=123,
        session=session,
    )

    assert response.status_code == 200
    persist.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert persist.await_args.kwargs["request_id"].startswith("gateway_")


@pytest.mark.asyncio
async def test_telegram_webhook_commits_dedup_without_enqueue(mocker, monkeypatch):
    session = mocker.AsyncMock()
    session.get.return_value = _account()
    monkeypatch.setattr(routes, "persist_inbound_event", mocker.AsyncMock(return_value=None))

    request = RequestStub(
        {"update_id": 10, "message": {"message_id": 7}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )

    response = await _call_webhook(
        request=request,
        account_id=123,
        session=session,
    )

    assert response.status_code == 200
    session.commit.assert_awaited_once()


def test_telegram_webhook_does_not_use_slowapi_limiter():
    route_source = inspect.getsource(routes)

    assert "@limiter.limit" not in route_source

