"""The board pack's checks on what the answer says, run on a scripted app: whether it says what it assumed is graded, not checked."""

import io
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

from tests.live import test_board_pack as board_pack
from tests.live.turn_renders import RENDER

pytestmark = pytest.mark.unit

# DeepSeek V4 Pro's turn-1 answer in the 7 Oct 2026 sweep pilot: a named PDF, its reason given in other words.
DEEPSEEK = (
    'Done. I made a one-page board memo as a PDF (ready to send as-is), "Board '
    "update, Q3 2026\", saved in Studio. If you'd rather have this as a Word "
    "draft you can edit, or as a slide deck instead, say the word and I'll "
    "convert or re-shape it."
)


@dataclass
class _ScriptedApp:
    """The app as the case drives it: each turn renders the next version of one PDF and answers as scripted."""

    answers: list[str]
    run: Any = field(
        default_factory=lambda: SimpleNamespace(
            model=SimpleNamespace(reads_images=False), metrics={}
        )
    )
    turns: int = 0

    async def note(self, title: str, text: str) -> int:
        return 1

    async def upload(self, name: str, data: bytes) -> int:
        return 2

    async def wait_ready(self, *document_ids: int) -> None:
        return None

    async def thread(self) -> int:
        return 1

    async def turn(self, thread_id: int, text: str) -> list[dict[str, Any]]:
        self.turns += 1
        return [
            {
                "type": "agent-step",
                "tool": RENDER,
                "id": f"render-{self.turns}",
                "status": "completed",
                "artifact": {"id": self.turns},
            },
            {"type": "delta", "text": self.answers[self.turns - 1]},
        ]

    async def artifacts(self) -> list[dict[str, Any]]:
        return [
            {
                "id": number,
                "status": "ready",
                "format": "pdf",
                "version": {"root_id": 1, "number": number},
            }
            for number in range(1, self.turns + 1)
        ]

    async def file(self, artifact_id: int) -> bytes:
        styles = getSampleStyleSheet()
        out = io.BytesIO()
        SimpleDocTemplate(out).build(
            [
                Paragraph("Board update, Q3 2026", styles["Title"]),
                Paragraph("Revenue rose 18% on a year ago.", styles["BodyText"]),
                Paragraph("Decisions needed", styles["Heading2"]),
                Paragraph("Approve the 8% higher band.", styles["BodyText"]),
            ]
        )
        return out.getvalue()


async def test_an_answer_that_words_its_assumption_its_own_way_passes_and_is_graded() -> (
    None
):
    """DeepSeek named the PDF and why, without "I chose" or "assumed": that is a quality grade, not a failure."""
    app = _ScriptedApp([DEEPSEEK, "Added a short Decisions needed section at the end."])

    await board_pack.test_the_agent_turns_a_vague_ask_into_a_board_document(app)  # type: ignore[arg-type]

    assert app.run.metrics == {"says_what_it_assumed": False}


async def test_an_answer_that_says_what_it_assumed_is_graded_so() -> None:
    """The words the ladder took stay the grade's measure."""
    app = _ScriptedApp(
        [
            "I went with a PDF, since a board pack is read, not edited.",
            "Added the decisions at the end.",
        ]
    )

    await board_pack.test_the_agent_turns_a_vague_ask_into_a_board_document(app)  # type: ignore[arg-type]

    assert app.run.metrics == {"says_what_it_assumed": True}


async def test_an_answer_that_never_names_the_format_still_fails() -> None:
    """Gemma's first board pack in the pilot: a "board report", neither Word nor PDF named."""
    app = _ScriptedApp(
        [
            "I have created a professional one-page board report for Kestrel Data Works.",
            "Done.",
        ]
    )

    with pytest.raises(AssertionError, match="does not say what it made"):
        await board_pack.test_the_agent_turns_a_vague_ask_into_a_board_document(app)  # type: ignore[arg-type]
