"""Chat on a Claude plan against the developer's own signed-in Claude Code."""

import io
import json
from pathlib import Path

import pytest
from PIL import Image as PILImage

from modules.llm.providers.types import Image, Message
from modules.llm.subscriptions.claude.chat import ClaudePlanProvider
from modules.llm.subscriptions.claude.chat_runs import ChatRuns
from modules.llm.subscriptions.claude.run import open_run

pytestmark = pytest.mark.claude_code
MODEL = "claude-haiku-5-5"
SYSTEM = Message("system", "You are SurfSense. Answer in as few words as possible.")


def _provider(
    claude_binary: Path, tmp_path: Path, runs: ChatRuns
) -> ClaudePlanProvider:
    return ClaudePlanProvider(
        runs=runs, work_dir=tmp_path, find_claude=lambda: claude_binary
    )


async def _text(provider: ClaudePlanProvider, messages: list[Message], **kw) -> str:
    return "".join([t async for t in provider.chat(MODEL, messages, **kw)])


async def test_a_conversation_is_answered_and_remembered(
    claude_binary: Path, tmp_path: Path
) -> None:
    """The second message goes to the warm run, which still knows the first."""
    runs = ChatRuns(open_run)
    provider = _provider(claude_binary, tmp_path, runs)
    first = [SYSTEM, Message("user", "My cat is called Biscuit. Reply ok.")]
    try:
        reply = await _text(provider, first, conversation="t1")
        name = await _text(
            provider,
            [
                *first,
                Message("assistant", reply),
                Message("user", "What is my cat called?"),
            ],
            conversation="t1",
        )
    finally:
        await runs.close_all()

    assert "biscuit" in name.lower()


async def test_a_schema_is_answered_as_json(
    claude_binary: Path, tmp_path: Path
) -> None:
    """What the chat router and Studio's workflows ask for."""
    runs = ChatRuns(open_run)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["tool"],
        "properties": {
            "tool": {"type": "string", "enum": ["weather", "notes", "none"]}
        },
    }
    try:
        text = await _text(
            _provider(claude_binary, tmp_path, runs),
            [SYSTEM, Message("user", "Pick the tool for: will it rain in Pune?")],
            json_schema=schema,
        )
    finally:
        await runs.close_all()

    assert json.loads(text) == {"tool": "weather"}


async def test_an_image_reaches_the_model(claude_binary: Path, tmp_path: Path) -> None:
    """Sent beside the message, not dropped."""
    picture = io.BytesIO()
    PILImage.new("RGB", (64, 64), (220, 20, 20)).save(picture, "PNG")
    runs = ChatRuns(open_run)
    try:
        text = await _text(
            _provider(claude_binary, tmp_path, runs),
            [
                SYSTEM,
                Message(
                    "user",
                    "What single colour fills this image? One word.",
                    images=(Image("image/png", picture.getvalue()),),
                ),
            ],
        )
    finally:
        await runs.close_all()

    assert "red" in text.lower()
