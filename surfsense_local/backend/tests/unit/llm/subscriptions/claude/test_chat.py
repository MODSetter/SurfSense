import json
from pathlib import Path

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    RateLimitEvent,
    RateLimitInfo,
    SystemMessage,
    TextBlock,
)

from modules.egress.service import EgressDeniedError
from modules.llm.providers.openai_responses.errors import (
    PlanLimitError,
    SignInRequiredError,
)
from modules.llm.providers.types import Delta, Image, Message
from modules.llm.subscriptions.claude.chat import ClaudePlanProvider
from modules.llm.subscriptions.claude.chat_runs import ChatRuns
from tests.claude_run_stand_in import ScriptedRun, answer, done

pytestmark = pytest.mark.unit
SYSTEM = Message("system", "You are SurfSense.")


class Opener:
    """Hands out scripted runs in order, recording the options each was opened with."""

    def __init__(self, *runs: ScriptedRun) -> None:
        self.runs = list(runs)
        self.opened: list[ScriptedRun] = []

    async def __call__(self, options: object) -> ScriptedRun:
        run = self.runs.pop(0)
        run.options = options
        self.opened.append(run)
        return run


def _provider(
    opener: Opener, tmp_path: Path, *, capacity: int = 4
) -> ClaudePlanProvider:
    return ClaudePlanProvider(
        runs=ChatRuns(opener, capacity=capacity),
        find_claude=lambda: Path("/home/ada/.local/bin/claude"),
        work_dir=tmp_path,
    )


async def _deltas(
    provider: ClaudePlanProvider, messages: list[Message], **kw
) -> list[Delta]:
    return [d async for d in provider.chat_deltas("claude-sonnet-5-5", messages, **kw)]


async def test_the_answer_streams_as_claude_code_writes_it(tmp_path: Path) -> None:
    """Each text delta reaches the chat as it arrives."""
    provider = _provider(Opener(ScriptedRun([answer("Hel", "lo")])), tmp_path)

    deltas = await _deltas(provider, [SYSTEM, Message("user", "Hi")])

    assert [d.text for d in deltas] == ["Hel", "lo"]


async def test_a_chat_run_has_no_tools_and_surfsenses_prompt(tmp_path: Path) -> None:
    """ADR 0052: the chat model never calls a tool; nothing is written to ~/.claude."""
    opener = Opener(ScriptedRun([answer("ok")]))

    await _deltas(_provider(opener, tmp_path), [SYSTEM, Message("user", "Hi")])

    options = opener.opened[0].options
    assert options.tools == []
    assert options.max_turns == 1
    assert options.system_prompt == "You are SurfSense."
    assert options.model == "claude-sonnet-5-5"
    assert options.include_partial_messages is True
    assert "no-session-persistence" in options.extra_args
    assert options.cwd == str(tmp_path)


async def test_a_new_conversation_sends_its_history_with_the_newest_message_last(
    tmp_path: Path,
) -> None:
    """A run that has not seen the conversation is told it as text."""
    opener = Opener(ScriptedRun([answer("Biscuit")]))
    history = [
        SYSTEM,
        Message("user", "My cat is Biscuit."),
        Message("assistant", "Nice name!"),
        Message("user", "What is my cat called?"),
    ]

    await _deltas(_provider(opener, tmp_path), history, conversation="t1")

    sent = opener.opened[0].sent[0]
    assert "My cat is Biscuit." in sent
    assert "Nice name!" in sent
    assert sent.rstrip().endswith("What is my cat called?")
    assert sent.index("Biscuit.") < sent.index("Nice name!")


async def test_the_next_message_of_a_conversation_reuses_its_run(
    tmp_path: Path,
) -> None:
    """A warm run already holds the history, so only the new message is sent."""
    run = ScriptedRun([answer("Nice name!"), answer("Biscuit")])
    opener = Opener(run)
    provider = _provider(opener, tmp_path)
    first = [SYSTEM, Message("user", "My cat is Biscuit.")]
    await _deltas(provider, first, conversation="t1")

    await _deltas(
        provider,
        [*first, Message("assistant", "Nice name!"), Message("user", "Her name?")],
        conversation="t1",
    )

    assert len(opener.opened) == 1
    assert run.sent[1] == "Her name?"


async def test_an_edited_conversation_starts_a_fresh_run(tmp_path: Path) -> None:
    """A retried or edited message leaves the warm run's memory wrong."""
    old, new = ScriptedRun([answer("a")]), ScriptedRun([answer("b")])
    opener = Opener(old, new)
    provider = _provider(opener, tmp_path)
    await _deltas(provider, [SYSTEM, Message("user", "First try")], conversation="t1")

    await _deltas(provider, [SYSTEM, Message("user", "Second try")], conversation="t1")

    assert old.closed
    assert new.sent[0].rstrip().endswith("Second try")


async def test_thinking_is_marked_apart_and_left_out_of_the_answer(
    tmp_path: Path,
) -> None:
    """Shown only with display=summarized; chat() keeps the answer alone."""
    script = [
        answer("42", thinking=["6 times 7"]),
        answer("42", thinking=["6 times 7"]),
    ]
    opener = Opener(ScriptedRun(script[:1]), ScriptedRun(script[1:]))
    provider = _provider(opener, tmp_path)
    messages = [SYSTEM, Message("user", "6x7?")]

    deltas = await _deltas(provider, messages, reasoning=True)
    text = [
        t async for t in provider.chat("claude-sonnet-5-5", messages, reasoning=True)
    ]

    assert deltas == [Delta("6 times 7", reasoning=True), Delta("42")]
    assert text == ["42"]
    assert opener.opened[0].options.thinking == {
        "type": "adaptive",
        "display": "summarized",
    }


async def test_a_schema_returns_claude_codes_structured_output(tmp_path: Path) -> None:
    """Claude Code answers a schema through its own tool, so it needs more than one turn."""
    schema = {"type": "object", "properties": {"tool": {"type": "string"}}}
    opener = Opener(ScriptedRun([[done(structured_output={"tool": "none"})]]))

    deltas = await _deltas(
        _provider(opener, tmp_path),
        [SYSTEM, Message("user", "pick")],
        json_schema=schema,
    )

    assert json.loads("".join(d.text for d in deltas)) == {"tool": "none"}
    options = opener.opened[0].options
    assert options.output_format == {"type": "json_schema", "schema": schema}
    assert options.max_turns == 3


async def test_a_signed_out_claude_code_asks_to_sign_in(tmp_path: Path) -> None:
    """Signed out in a terminal after connecting: the chat offers the sign-in notice."""
    signed_out = AssistantMessage(
        content=[TextBlock("Not logged in")], model="x", error="authentication_failed"
    )
    opener = Opener(ScriptedRun([[signed_out, done(is_error=True)]]))

    with pytest.raises(SignInRequiredError):
        await _deltas(_provider(opener, tmp_path), [SYSTEM, Message("user", "Hi")])


async def test_a_used_up_plan_is_the_plan_limit(tmp_path: Path) -> None:
    """Raised before any text, so the chat shows the limit, not half an answer."""
    info = RateLimitInfo(status="rejected", resets_at=1792107600)
    limit = RateLimitEvent(rate_limit_info=info, uuid="u", session_id="s")
    opener = Opener(ScriptedRun([[limit, done(is_error=True)]]))

    with pytest.raises(PlanLimitError):
        await _deltas(_provider(opener, tmp_path), [SYSTEM, Message("user", "Hi")])


async def test_no_claude_code_asks_to_set_it_up(tmp_path: Path) -> None:
    """Uninstalled after connecting: the chat shows the sign-in notice, not a crash."""
    provider = ClaudePlanProvider(
        runs=ChatRuns(Opener(), capacity=4), find_claude=lambda: None, work_dir=tmp_path
    )

    with pytest.raises(SignInRequiredError):
        await _deltas(provider, [SYSTEM, Message("user", "Hi")])


async def test_a_token_cap_and_temperature_are_dropped(tmp_path: Path) -> None:
    """Claude Code exposes neither; refusing them would break every caller that sets one."""
    provider = _provider(Opener(ScriptedRun([answer("ok")])), tmp_path)

    deltas = await _deltas(
        provider, [SYSTEM, Message("user", "Hi")], max_tokens=64, temperature=0.2
    )

    assert [d.text for d in deltas] == ["ok"]


async def test_the_least_recently_used_run_is_closed_past_the_cap(
    tmp_path: Path,
) -> None:
    """At most this many Claude Code processes stay warm."""
    first, second, third = (ScriptedRun([answer("x")]) for _ in range(3))
    provider = _provider(Opener(first, second, third), tmp_path, capacity=2)

    for name in ("a", "b", "c"):
        await _deltas(provider, [SYSTEM, Message("user", name)], conversation=name)

    assert first.closed
    assert not second.closed
    assert not third.closed


async def test_an_image_goes_beside_the_newest_message(tmp_path: Path) -> None:
    """Sent as an image block, never dropped: the manifest says the model reads images."""
    opener = Opener(ScriptedRun([answer("A cat")]))
    picture = Image("image/png", b"\x89PNG")

    await _deltas(
        _provider(opener, tmp_path),
        [SYSTEM, Message("user", "What is this?", images=(picture,))],
    )

    blocks = opener.opened[0].sent[0]
    assert blocks[-1] == {"type": "text", "text": "What is this?"}
    assert blocks[0]["type"] == "image"
    assert blocks[0]["source"]["media_type"] == "image/png"


async def test_the_models_window_comes_from_the_manifest(tmp_path: Path) -> None:
    """Haiku 5.5 is not in the manifest yet, so its window is unknown, not zero."""
    provider = _provider(Opener(), tmp_path)

    assert await provider.context_tokens("claude-sonnet-5-5") == 1_000_000
    assert await provider.context_tokens("claude-haiku-5-5") is None


async def test_a_run_left_idle_is_closed(tmp_path: Path) -> None:
    """A conversation nobody answers for five minutes gives its process back."""
    now = [0.0]
    idle, later = ScriptedRun([answer("x")]), ScriptedRun([answer("y")])
    provider = ClaudePlanProvider(
        runs=ChatRuns(Opener(idle, later), idle_seconds=300, clock=lambda: now[0]),
        find_claude=lambda: Path("/home/ada/.local/bin/claude"),
        work_dir=tmp_path,
    )
    await _deltas(provider, [SYSTEM, Message("user", "a")], conversation="a")

    now[0] = 301.0
    await _deltas(provider, [SYSTEM, Message("user", "b")], conversation="b")

    assert idle.closed


async def test_a_message_sent_while_its_run_is_busy_gets_a_run_of_its_own(
    tmp_path: Path,
) -> None:
    """Two tabs on one thread: the second answers from the whole conversation."""
    busy, other = ScriptedRun([answer("1")]), ScriptedRun([answer("2")])
    provider = _provider(Opener(busy, other), tmp_path)
    first = [SYSTEM, Message("user", "a")]
    stream = provider.chat_deltas("claude-sonnet-5-5", first, conversation="t1")
    await anext(stream)

    second = await _deltas(
        provider,
        [*first, Message("assistant", "1"), Message("user", "b")],
        conversation="t1",
    )
    await stream.aclose()

    assert [d.text for d in second] == ["2"]
    assert other.closed
    assert other.sent[0].rstrip().endswith("b")


async def test_a_host_turned_off_mid_reply_stops_the_run_at_its_first_retry(
    tmp_path: Path,
) -> None:
    """Rather than after Claude Code's ten retries."""
    retry = SystemMessage(subtype="api_retry", data={"attempt": 1})
    refusal = EgressDeniedError("host:api.anthropic.com")
    run = ScriptedRun([[retry, *answer("never")]])

    async def host_off() -> EgressDeniedError | None:
        return refusal

    provider = ClaudePlanProvider(
        runs=ChatRuns(Opener(run)),
        find_claude=lambda: Path("/home/ada/.local/bin/claude"),
        work_dir=tmp_path,
        proxy_refusal=host_off,
    )

    with pytest.raises(EgressDeniedError):
        await _deltas(provider, [SYSTEM, Message("user", "Hi")])
