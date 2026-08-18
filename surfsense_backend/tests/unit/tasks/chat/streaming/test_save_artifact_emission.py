"""Only successful saves publish product-card output."""

from __future__ import annotations

import importlib


class _FakeStreaming:
    def format_terminal_info(self, text: str, message_type: str = "info") -> str:
        return f"TERM::{message_type}::{text}"


class _FakeContext:
    def __init__(self, tool_output: object) -> None:
        self.tool_output = tool_output
        self.cards: list[dict] = []
        self.streaming_service = _FakeStreaming()

    def emit_tool_output_card(self, payload: dict) -> str:
        self.cards.append(payload)
        return "CARD"


def _frames(output: object) -> tuple[_FakeContext, list[str]]:
    context = _FakeContext(output)
    module = importlib.import_module(
        "app.tasks.chat.streaming.handlers.tools.deliverables.save_artifact.emission"
    )
    return context, list(module.iter_completion_emission_frames(context))


def test_successful_save_emits_product_card():
    output = {"status": "saved", "artifact_id": 12, "title": "Report"}

    context, frames = _frames(output)

    assert context.cards == [output]
    assert frames == ["CARD", "TERM::success::Artifact saved: Report"]


def test_failed_save_emits_only_terminal_process_output():
    context, frames = _frames({"status": "failed", "error": "disk full"})

    assert context.cards == []
    assert frames == ["TERM::error::Artifact save failed: disk full"]


def test_non_mapping_save_output_emits_no_product_card():
    context, frames = _frames("cancelled")

    assert context.cards == []
    assert frames == ["TERM::error::Artifact save failed: Unknown error"]
