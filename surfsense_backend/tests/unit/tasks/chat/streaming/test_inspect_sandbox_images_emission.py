"""The page-review card needs the QA report, not just its length."""

from __future__ import annotations

import importlib

from app.tasks.chat.streaming.handlers.tools.registry import _import_emission


class _FakeStreaming:
    def format_terminal_info(self, text: str, message_type: str = "info") -> str:
        return f"TERM::{message_type}"


class _FakeCtx:
    def __init__(self, tool_output: object) -> None:
        self.tool_name = "inspect_sandbox_images"
        self.tool_output = tool_output
        self.cards: list[dict] = []
        self.streaming_service = _FakeStreaming()

    def emit_tool_output_card(self, payload: dict) -> str:
        self.cards.append(payload)
        return "CARD"


def test_tool_resolves_to_its_own_emission_handler():
    """Falling back to default.emission drops the report and empties the card."""
    module = _import_emission("inspect_sandbox_images")

    assert module.__name__.endswith("inspect_sandbox_images.emission")


def test_card_carries_the_report():
    report = "## page-1.jpg\nFooter overlaps the bottom margin."
    ctx = _FakeCtx({"result": report})
    module = importlib.import_module(
        "app.tasks.chat.streaming.handlers.tools.inspect_sandbox_images.emission"
    )

    list(module.iter_completion_emission_frames(ctx))

    assert ctx.cards == [{"result": report}]


def test_plain_string_output_is_forwarded():
    ctx = _FakeCtx("## page-1.jpg\nClean.")
    module = importlib.import_module(
        "app.tasks.chat.streaming.handlers.tools.inspect_sandbox_images.emission"
    )

    list(module.iter_completion_emission_frames(ctx))

    assert ctx.cards == [{"result": "## page-1.jpg\nClean."}]
