from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import time
from types import SimpleNamespace

import pytest

from app.db import ExternalChatAccount, ExternalChatAccountMode, ExternalChatPlatform
from app.routes import gateway_webhook_routes as routes


@pytest.fixture(autouse=True)
def _enable_gateways(monkeypatch):
    """Turn on the Telegram/Slack/Discord gateway flags the routes gate on.

    The routes early-return when their integration is unconfigured, so without
    this the handlers never reach the logic these tests assert on.
    """
    monkeypatch.setattr(routes.config, "GATEWAY_TELEGRAM_INTAKE_MODE", "webhook")
    monkeypatch.setattr(routes.config, "TELEGRAM_SHARED_BOT_TOKEN", "telegram-token")
    monkeypatch.setattr(routes.config, "TELEGRAM_SHARED_BOT_USERNAME", "surf_bot")
    monkeypatch.setattr(routes.config, "TELEGRAM_WEBHOOK_SECRET", "telegram-webhook-secret")

    monkeypatch.setattr(routes.config, "GATEWAY_SLACK_ENABLED", True)
    monkeypatch.setattr(routes.config, "GATEWAY_SLACK_CLIENT_ID", "slack-client")
    monkeypatch.setattr(routes.config, "GATEWAY_SLACK_CLIENT_SECRET", "slack-secret")
    monkeypatch.setattr(routes.config, "GATEWAY_SLACK_SIGNING_SECRET", "signing-secret")

    monkeypatch.setattr(routes.config, "GATEWAY_DISCORD_ENABLED", True)
    monkeypatch.setattr(routes.config, "DISCORD_CLIENT_ID", "discord-client")
    monkeypatch.setattr(routes.config, "DISCORD_CLIENT_SECRET", "discord-secret")
    monkeypatch.setattr(routes.config, "DISCORD_BOT_TOKEN", "discord-bot-token")


class RequestStub:
    def __init__(self, payload=None, *, headers=None, json_exc: Exception | None = None):
        self.headers = headers or {}
        self._payload = payload
        self._json_exc = json_exc

    async def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._payload

    async def body(self):
        return json.dumps(self._payload).encode()


def _account(secret: str = "secret") -> ExternalChatAccount:
    return ExternalChatAccount(
        id=123,
        platform=ExternalChatPlatform.TELEGRAM,
        webhook_secret=secret,
        bot_username="surf_bot",
    )


def _slack_account() -> ExternalChatAccount:
    return ExternalChatAccount(
        id=456,
        platform=ExternalChatPlatform.SLACK,
        mode=ExternalChatAccountMode.CLOUD_SHARED,
        is_system_account=True,
        cursor_state={"team_id": "T123", "bot_user_id": "U_BOT"},
    )


def _signed_slack_request(payload: dict, *, secret: str = "signing-secret") -> RequestStub:
    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(
        secret.encode(),
        b"v0:" + timestamp.encode() + b":" + body,
        hashlib.sha256,
    ).hexdigest()

    class SlackRequestStub(RequestStub):
        async def body(self):
            return body

    return SlackRequestStub(
        payload,
        headers={
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": f"v0={digest}",
        },
    )


def _enable_slack_gateway(monkeypatch):
    monkeypatch.setattr(routes.config, "GATEWAY_SLACK_ENABLED", True)
    monkeypatch.setattr(routes.config, "GATEWAY_SLACK_CLIENT_ID", "client-id")
    monkeypatch.setattr(routes.config, "GATEWAY_SLACK_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(routes.config, "GATEWAY_SLACK_SIGNING_SECRET", "signing-secret")


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


def test_verify_slack_signature_accepts_valid_signature():
    payload = b'{"type":"event_callback"}'
    timestamp = str(int(time.time()))
    digest = hmac.new(
        b"secret",
        b"v0:" + timestamp.encode() + b":" + payload,
        hashlib.sha256,
    ).hexdigest()

    assert routes.verify_slack_signature(
        signing_secret="secret",
        timestamp=timestamp,
        signature=f"v0={digest}",
        body=payload,
    )


@pytest.mark.asyncio
async def test_slack_webhook_url_verification(monkeypatch, mocker):
    _enable_slack_gateway(monkeypatch)
    request = _signed_slack_request({"type": "url_verification", "challenge": "abc123"})

    response = await routes.slack_webhook(request=request, session=mocker.AsyncMock())

    assert response.status_code == 200
    assert json.loads(response.body)["challenge"] == "abc123"


@pytest.mark.asyncio
async def test_slack_webhook_persists_event(monkeypatch, mocker):
    _enable_slack_gateway(monkeypatch)
    session = mocker.AsyncMock()
    monkeypatch.setattr(routes, "get_slack_account_by_team", mocker.AsyncMock(return_value=_slack_account()))
    persist = mocker.AsyncMock(return_value=100)
    monkeypatch.setattr(routes, "persist_inbound_event", persist)
    payload = {
        "type": "event_callback",
        "team_id": "T123",
        "event_id": "Ev123",
        "event": {
            "type": "app_mention",
            "channel": "C123",
            "user": "U123",
            "text": "<@U_BOT> hello",
            "ts": "1717000000.000100",
        },
    }
    request = _signed_slack_request(payload)

    response = await routes.slack_webhook(request=request, session=session)

    assert response.status_code == 200
    persist.assert_awaited_once()
    assert persist.await_args.kwargs["event_dedupe_key"] == "slack_event:Ev123"
    assert persist.await_args.kwargs["platform"] == ExternalChatPlatform.SLACK
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_slack_webhook_ignores_self_event(monkeypatch, mocker):
    _enable_slack_gateway(monkeypatch)
    session = mocker.AsyncMock()
    monkeypatch.setattr(routes, "get_slack_account_by_team", mocker.AsyncMock(return_value=_slack_account()))
    persist = mocker.AsyncMock(return_value=100)
    monkeypatch.setattr(routes, "persist_inbound_event", persist)
    request = _signed_slack_request(
        {
            "type": "event_callback",
            "team_id": "T123",
            "event_id": "Ev123",
            "event": {
                "type": "app_mention",
                "channel": "C123",
                "user": "U_BOT",
                "text": "loop",
                "ts": "1717000000.000100",
            },
        }
    )

    response = await routes.slack_webhook(request=request, session=session)

    assert response.status_code == 200
    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_discord_gateway_install_returns_oauth_url(monkeypatch, mocker):
    monkeypatch.setattr(routes.config, "DISCORD_CLIENT_ID", "discord-client")
    monkeypatch.setattr(
        routes.config,
        "GATEWAY_DISCORD_REDIRECT_URI",
        "http://localhost:8000/api/v1/gateway/discord/callback",
    )
    monkeypatch.setattr(routes.config, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(routes, "check_search_space_access", mocker.AsyncMock())

    response = await routes.install_discord_gateway(
        search_space_id=123,
        user=SimpleNamespace(id="00000000-0000-0000-0000-000000000001"),
        session=mocker.AsyncMock(),
    )

    assert response["auth_url"].startswith("https://discord.com/api/oauth2/authorize?")
    assert "client_id=discord-client" in response["auth_url"]
    assert "gateway%2Fdiscord%2Fcallback" in response["auth_url"]
    assert "scope=identify+guilds+bot" in response["auth_url"]


def test_discord_gateway_callback_does_not_create_search_source_connector():
    callback_source = inspect.getsource(routes.discord_gateway_callback)

    assert "SearchSourceConnector" not in callback_source

