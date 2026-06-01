from __future__ import annotations

from app.gateway.slack.adapter import SlackAdapter


def test_slack_adapter_parses_app_mention_and_strips_bot_mention():
    adapter = SlackAdapter("xoxb-test", bot_user_id="U_BOT")

    parsed = adapter.parse_inbound(
        {
            "team_id": "T123",
            "event": {
                "type": "app_mention",
                "channel": "C123",
                "user": "U123",
                "text": "<@U_BOT> summarize this thread",
                "ts": "1717000000.000100",
            },
        }
    )

    assert parsed.platform == "slack"
    assert parsed.text == "summarize this thread"
    assert parsed.external_peer_id == "slack_thread:T123:C123:1717000000.000100"
    assert parsed.metadata["slack_user_peer_id"] == "slack_user:T123:U123"
    assert parsed.metadata["thread_ts"] == "1717000000.000100"


def test_slack_adapter_uses_existing_thread_ts():
    adapter = SlackAdapter("xoxb-test", bot_user_id="U_BOT")

    parsed = adapter.parse_inbound(
        {
            "team_id": "T123",
            "event": {
                "type": "app_mention",
                "channel": "C123",
                "user": "U123",
                "text": "<@U_BOT> continue",
                "ts": "1717000001.000200",
                "thread_ts": "1717000000.000100",
            },
        }
    )

    assert parsed.external_peer_id == "slack_thread:T123:C123:1717000000.000100"
    assert parsed.metadata["message_ts"] == "1717000001.000200"
