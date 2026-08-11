"""The verification card needs the complete backend verdict."""

from __future__ import annotations

import importlib

from app.tasks.chat.streaming.handlers.tools.registry import _import_emission


class _FakeStreaming:
    def format_terminal_info(self, text: str, message_type: str = "info") -> str:
        return f"TERM::{message_type}::{text}"


class _FakeCtx:
    def __init__(self, tool_output: object) -> None:
        self.tool_name = "verify_artifact"
        self.tool_output = tool_output
        self.cards: list[dict] = []
        self.streaming_service = _FakeStreaming()

    def emit_tool_output_card(self, payload: dict) -> str:
        self.cards.append(payload)
        return "CARD"


def test_tool_resolves_to_its_own_emission_handler():
    module = _import_emission("verify_artifact")

    assert module.__name__.endswith("verify_artifact.emission")


def test_card_carries_the_complete_verdict():
    verdict = {
        "status": "failed",
        "findings": ["Footer is clipped"],
        "preview_path": "/tmp/report.pdf",
        "page_count": 2,
    }
    ctx = _FakeCtx(verdict)
    module = importlib.import_module(
        "app.tasks.chat.streaming.handlers.tools.verify_artifact.emission"
    )

    frames = list(module.iter_completion_emission_frames(ctx))

    assert ctx.cards == [verdict]
    assert frames[-1].startswith("TERM::error")


def test_unavailable_visual_review_is_not_emitted_as_success():
    verdict = {
        "status": "verified",
        "findings": [],
        "verification_unavailable": "No vision-capable model is configured",
    }
    ctx = _FakeCtx(verdict)
    module = importlib.import_module(
        "app.tasks.chat.streaming.handlers.tools.verify_artifact.emission"
    )

    frames = list(module.iter_completion_emission_frames(ctx))

    assert frames[-1] == (
        "TERM::info::Artifact verification completed without visual review"
    )
