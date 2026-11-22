from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage, StreamEvent

from modules.llm.subscriptions.claude.launch import launch_options
from modules.llm.subscriptions.claude.run import open_run

pytestmark = pytest.mark.claude_code


def _options(binary: Path, tmp_path: Path, **per_run: object):
    return launch_options(
        binary,
        proxy_url=None,
        model="haiku",
        tools=[],
        cwd=str(tmp_path),
        include_partial_messages=True,
        **per_run,
    )


def _text(messages: list) -> str:
    return "".join(
        m.event["delta"].get("text", "")
        for m in messages
        if isinstance(m, StreamEvent) and m.event.get("type") == "content_block_delta"
    )


async def test_a_run_answers_with_surfsenses_prompt(
    claude_binary: Path, tmp_path: Path
) -> None:
    """With every tool off, the model follows SurfSense's system prompt, not Claude Code's."""
    run = await open_run(
        _options(claude_binary, tmp_path, system_prompt="Reply with exactly: SURFSENSE")
    )
    try:
        messages = [m async for m in run.send("Hello")]
    finally:
        await run.close()

    assert "SURFSENSE" in _text(messages)
    assert isinstance(messages[-1], ResultMessage)
    assert not messages[-1].is_error


async def test_a_schema_comes_back_as_structured_output(
    claude_binary: Path, tmp_path: Path
) -> None:
    """Claude Code returns a schema's answer through its own tool, so it needs turns."""
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["city"],
        "properties": {"city": {"type": "string"}},
    }
    run = await open_run(
        _options(
            claude_binary,
            tmp_path,
            max_turns=3,
            output_format={"type": "json_schema", "schema": schema},
        )
    )
    try:
        messages = [m async for m in run.send("Which city: 'rain in Pune tomorrow'?")]
    finally:
        await run.close()

    assert messages[-1].structured_output == {"city": "Pune"}


async def test_a_stopped_run_answers_the_next_message(
    claude_binary: Path, tmp_path: Path
) -> None:
    """Stop ends the turn, not the run."""
    run = await open_run(_options(claude_binary, tmp_path))
    try:
        stopped = []
        async for message in run.send("Count slowly from 1 to 300, one per line."):
            stopped.append(message)
            if len(stopped) == 10:
                await run.interrupt()
        after = [m async for m in run.send("Reply with exactly: AGAIN")]
    finally:
        await run.close()

    assert stopped[-1].is_error
    assert "AGAIN" in _text(after)


async def test_a_later_run_resumes_a_session(
    claude_binary: Path, tmp_path: Path
) -> None:
    """A reopened agent thread continues the session it had."""
    first = await open_run(_options(claude_binary, tmp_path))
    try:
        said = [m async for m in first.send("Remember the word KESTREL. Reply ok.")]
    finally:
        await first.close()

    later = await open_run(
        _options(claude_binary, tmp_path, resume=said[-1].session_id)
    )
    try:
        answer = [m async for m in later.send("Which word did I ask you to remember?")]
    finally:
        await later.close()

    assert "KESTREL" in _text(answer).upper()


async def test_the_models_are_claude_codes_own_list(
    claude_binary: Path, tmp_path: Path
) -> None:
    """The picker lists what the account's Claude Code offers."""
    run = await open_run(_options(claude_binary, tmp_path))
    try:
        models = await run.models()
    finally:
        await run.close()

    assert {"opus", "sonnet", "haiku"} <= {m["value"] for m in models}
