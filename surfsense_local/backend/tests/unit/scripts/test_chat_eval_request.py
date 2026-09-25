"""The eval sends what the app's chat would send, built by chat's own code."""

import pytest
from chat_eval.cases import Case, Passage, Turn
from chat_eval.model import eval_model
from chat_eval.request import body, conversation

from modules.llm.profile import Tier
from modules.llm.prompting import load
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit


def test_a_curated_model_is_named_as_each_target_serves_it() -> None:
    """The router lists the default build's file; Featherless lists the source repo."""
    model = eval_model("qwen3-8b")

    assert model.local_name == "Qwen3-8B-UD-Q4_K_XL"
    assert model.featherless_name == "Qwen/Qwen3-8B"


def test_both_targets_get_the_prompt_tier_the_app_gives_the_local_build() -> None:
    """Featherless lists no sizes, so the app would give its models frontier prompts."""
    assert eval_model("qwen3-8b").tier is Tier.CAPABLE
    assert eval_model("qwen3-4b").tier is Tier.COMPACT


def test_sampling_is_the_publishers_thinking_set_or_gemmas_only_one() -> None:
    """Sent on both targets, so neither answers on its own server's defaults."""
    assert eval_model("qwen3-4b").sampling == {
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
    }
    assert eval_model("gemma-3-4b").sampling == {
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 64,
        "min_p": 0.01,
    }


async def test_a_case_becomes_the_turn_chat_would_send() -> None:
    """Chat's grounding with passages as [1] and [2], the history, then the question."""
    case = Case(
        id="follow-up",
        question="And the X300?",
        passages=[
            Passage(title="Kestrel manual", text="The X300 is covered for 39 months."),
            Passage(title="Kestrel manual", text="The X200 is covered for 27 months."),
        ],
        history=[
            Turn(role="user", text="How long is the X200 warranty?"),
            Turn(role="assistant", text="27 months."),
        ],
    )

    system, *rest = await conversation(case, Tier.COMPACT)

    assert system.role == "system"
    assert system.content.startswith(load("modules.chat", Tier.COMPACT))
    # Two chunks of one document are shown under it once, as chat groups them.
    assert system.content.count('<document title="Kestrel manual"') == 1
    assert "[1] The X300 is covered for 39 months." in system.content
    assert "[2] The X200 is covered for 27 months." in system.content
    assert [(m.role, m.content) for m in rest] == [
        ("user", "How long is the X200 warranty?"),
        ("assistant", "27 months."),
        ("user", "And the X300?"),
    ]


def test_the_answer_is_capped_at_the_reserve_chat_keeps_for_it() -> None:
    """1,024 tokens on both targets, unstreamed so the reply says why it stopped."""
    sent = body("Qwen/Qwen3-8B", [Message("user", "hi")], {"temperature": 0.6})

    assert sent == {
        "model": "Qwen/Qwen3-8B",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1024,
        "stream": False,
        "temperature": 0.6,
    }
