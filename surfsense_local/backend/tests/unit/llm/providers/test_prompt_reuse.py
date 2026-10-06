"""How much of each prompt the model reused rather than read again, in the log.

Measured at b11050: a streamed chat's last chunk carries `timings`, asked or
not, with `cache_n` the prompt tokens reused and `prompt_n` those read. A remote
endpoint that reports reuse puts it in `usage`, whose `prompt_tokens` counts
both.
"""

import logging

import httpx
import pytest

from modules.llm.providers.openai_compatible.chat import OpenAICompatibleChatProvider
from modules.llm.providers.openai_responses import PlanToken
from modules.llm.providers.openai_responses.chat import ResponsesChatProvider
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit

ANSWER = 'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
DONE = "data: [DONE]\n\n"


def _chat(body: str) -> OpenAICompatibleChatProvider:
    """An endpoint that streams `body` back to every request."""
    return OpenAICompatibleChatProvider(
        "http://local/v1",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body)),
    )


async def _answer(provider: object, model: str) -> None:
    """One turn, read to its end, which is when reuse is reported."""
    async for _ in provider.chat_deltas(model, [Message("user", "hi")]):
        pass


async def test_the_local_runtime_logs_how_much_of_the_prompt_it_reused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without it nobody can tell a prompt the runtime reused from one it read
    again, which is the difference between a second and a minute."""
    last = (
        'data: {"choices":[{"finish_reason":"stop","index":0,"delta":{}}],'
        '"timings":{"cache_n":5442,"prompt_n":34,"prompt_ms":654.1}}\n\n'
    )
    caplog.set_level(logging.INFO)

    await _answer(_chat(ANSWER + last + DONE), "qwen3")

    assert "qwen3 reused 5442 of 5476 prompt tokens" in caplog.text


async def test_a_remote_endpoint_that_reports_reuse_is_logged_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """OpenRouter sends usage on every stream; most others only when asked."""
    last = (
        'data: {"choices":[],"usage":{"prompt_tokens":2048,"completion_tokens":5,'
        '"prompt_tokens_details":{"cached_tokens":1920}}}\n\n'
    )
    caplog.set_level(logging.INFO)

    await _answer(_chat(ANSWER + last + DONE), "gpt-5")

    assert "gpt-5 reused 1920 of 2048 prompt tokens" in caplog.text


async def test_a_chatgpt_plan_logs_the_reuse_its_completed_reply_reports(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The Responses API reports it once, on `response.completed`."""
    completed = (
        'data: {"type":"response.completed","response":{"model":"gpt-5.5",'
        '"usage":{"input_tokens":3000,"input_tokens_details":{"cached_tokens":2944},'
        '"output_tokens":7}}}\n\n'
    )
    text = 'data: {"type":"response.output_text.delta","delta":"Hi"}\n\n'

    async def token(_: bool) -> str:
        """The plan's access token; never refreshed here."""
        return "token"

    plan = ResponsesChatProvider(
        "http://plan/codex",
        PlanToken(token),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, text=text + completed)
        ),
    )
    caplog.set_level(logging.INFO)

    await _answer(plan, "gpt-5.5")

    assert "gpt-5.5 reused 2944 of 3000 prompt tokens" in caplog.text
