"""Emission handlers for the capability chat tools (web_scrape / web_discover)."""

from __future__ import annotations

import importlib


class _FakeStreaming:
    def __init__(self) -> None:
        self.terminals: list[tuple[str, str]] = []

    def format_terminal_info(self, text: str, message_type: str = "info") -> str:
        self.terminals.append((text, message_type))
        return f"TERM::{message_type}"


class _FakeCtx:
    """Minimal stand-in for ToolCompletionEmissionContext (only what handlers use)."""

    def __init__(self, tool_output: object) -> None:
        self.tool_output = tool_output
        self.cards: list[dict] = []
        self.streaming_service = _FakeStreaming()

    def emit_tool_output_card(self, payload: dict) -> str:
        self.cards.append(payload)
        return "CARD"


def _scrape_frames(ctx: _FakeCtx) -> list[str]:
    mod = importlib.import_module(
        "app.tasks.chat.streaming.handlers.tools.web_scrape.emission"
    )
    return list(mod.iter_completion_emission_frames(ctx))


def _discover_frames(ctx: _FakeCtx) -> list[str]:
    mod = importlib.import_module(
        "app.tasks.chat.streaming.handlers.tools.web_discover.emission"
    )
    return list(mod.iter_completion_emission_frames(ctx))


def test_scrape_card_previews_content_and_summarizes():
    long_body = "x" * 2000
    ctx = _FakeCtx(
        {
            "rows": [
                {
                    "url": "https://a.com",
                    "status": "success",
                    "content": long_body,
                    "metadata": {"title": "A"},
                },
                {"url": "https://b.com", "status": "failed", "error": "boom"},
            ]
        }
    )

    _scrape_frames(ctx)

    [card] = ctx.cards
    assert card["succeeded"] == 1
    assert card["total"] == 2
    page = card["pages"][0]
    # full content must not be dumped into the card; a bounded preview is used
    assert "content" not in page
    assert len(page["content_preview"]) < len(long_body)
    assert page["metadata"] == {"title": "A"}
    assert card["pages"][1]["error"] == "boom"


def test_scrape_terminal_success_when_any_page_succeeds():
    ctx = _FakeCtx(
        {"rows": [{"url": "https://a.com", "status": "success", "content": "hi"}]}
    )

    _scrape_frames(ctx)

    assert ctx.streaming_service.terminals[-1][1] == "success"


def test_scrape_terminal_error_when_all_pages_fail():
    ctx = _FakeCtx(
        {"rows": [{"url": "https://a.com", "status": "failed", "error": "boom"}]}
    )

    _scrape_frames(ctx)

    assert ctx.streaming_service.terminals[-1][1] == "error"


def test_scrape_non_dict_output_is_an_error_card():
    ctx = _FakeCtx("Insufficient credit to continue.")

    _scrape_frames(ctx)

    assert ctx.cards[0]["status"] == "error"
    assert ctx.streaming_service.terminals[-1][1] == "error"


def test_discover_card_lists_hits_and_counts():
    ctx = _FakeCtx(
        {
            "hits": [
                {"url": "https://a.com", "title": "A", "snippet": "s", "provider": "p"},
                {
                    "url": "https://b.com",
                    "title": "B",
                    "snippet": None,
                    "provider": "p",
                },
            ]
        }
    )

    _discover_frames(ctx)

    [card] = ctx.cards
    assert card["count"] == 2
    assert card["hits"][0]["url"] == "https://a.com"
    assert ctx.streaming_service.terminals[-1][1] == "success"


def test_discover_non_dict_output_is_an_error_card():
    ctx = _FakeCtx("Search is not available.")

    _discover_frames(ctx)

    assert ctx.cards[0]["status"] == "error"
    assert ctx.streaming_service.terminals[-1][1] == "error"
