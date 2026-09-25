"""What the judge is shown about one reply, and what is kept of its verdict."""

import json
import re

import pytest
from chat_eval.judge.verdict import VERDICT_FORMAT, verdict_record, verdict_request

pytestmark = pytest.mark.unit

JUDGE = "anthropic/claude-opus"

VERDICT = {
    "grounded": True,
    "complete": True,
    "citations": False,
    "gaps": None,
    "language": True,
    "failures": [
        {
            "criterion": "citations",
            "quote": "[1] Ingrid Solheim proposed",
            "problem": "The label comes before the claim it supports.",
            "cause": "prompt_instruction",
            "fix": "Move 'Put the label right after the claim' to the first line.",
        }
    ],
    "summary": "Correct and grounded, with labels placed before their claims.",
}

RECORD = {
    "case": "single-fact",
    "repeat": 0,
    "model": "qwen3-1.7b",
    "tier": "compact",
    "messages": [
        {
            "role": "system",
            "content": "Cite with [n].\n\n<retrieved_context>\n"
            "  [1] Unopened items return within 30 days.\n"
            "  [2] The X200 is covered for 27 months.\n</retrieved_context>",
        },
        {"role": "user", "content": "How long is the X200 warranty?"},
    ],
    "reasoning": "The second passage states the warranty period.",
    "answer": "The X200 is covered for 27 months [2].",
    "answer_key": {"supporting": [2], "facts": ["27"]},
    "score": {
        "truncated": False,
        "empty": False,
        "invented": 0,
        "cites_support": True,
        "cites_other": False,
        "facts": True,
        "same_script": True,
    },
}


def test_the_judge_sees_what_the_model_saw_what_it_did_and_the_answer_key() -> None:
    """Without the prompt and the reasoning a verdict names a failure, not its cause."""
    rubric, question = verdict_request(RECORD)

    assert rubric.role == "system"
    assert "prompt_instruction" in rubric.content
    assert RECORD["messages"][0]["content"] in question.content
    assert "How long is the X200 warranty?" in question.content
    assert RECORD["reasoning"] in question.content
    assert RECORD["answer"] in question.content
    assert "qwen3-1.7b, on the compact prompt tier" in question.content
    assert "Passages that hold the answer: [2]" in question.content
    assert "A correct answer states: 27" in question.content
    assert '"cites_other": false' in question.content


def test_the_answer_key_says_so_when_no_passage_holds_the_answer() -> None:
    """Otherwise the judge cannot tell an honest 'not in the sources' from a miss."""
    unanswerable = {**RECORD, "answer_key": {"supporting": [], "facts": []}}

    _, question = verdict_request(unanswerable)

    assert "No passage holds the answer." in question.content
    assert "A correct answer states" not in question.content


def test_a_verdict_that_fits_the_schema_is_kept_with_its_reply_and_judge() -> None:
    """Runs are compared only under the same judge, so each verdict names it."""
    kept = verdict_record(RECORD, json.dumps(VERDICT), JUDGE)

    assert {key: kept[key] for key in ("case", "repeat", "judge", "verdict")} == {
        "case": "single-fact",
        "repeat": 0,
        "judge": JUDGE,
        "verdict": VERDICT,
    }


def test_a_verdict_names_the_rubric_it_was_judged_under() -> None:
    """A rubric edit changes the judge as much as a model swap does."""
    kept = verdict_record(RECORD, json.dumps(VERDICT), JUDGE)

    assert re.fullmatch(r"[0-9a-f]{8}", kept["rubric"])


def test_a_reply_that_does_not_fit_the_schema_is_kept_as_an_error() -> None:
    """One malformed verdict should not cost the rest of a paid run."""
    kept = verdict_record(RECORD, '{"grounded": "mostly"}', JUDGE)

    assert (kept["case"], kept["repeat"], kept["judge"]) == ("single-fact", 0, JUDGE)
    assert "verdict" not in kept
    assert "grounded" in kept["error"]


def test_the_schema_sent_to_the_judge_is_one_strict_mode_accepts() -> None:
    """Strict mode refuses an optional field or an open object, and says so only
    once a key is being spent."""
    assert VERDICT_FORMAT["json_schema"]["strict"] is True
    schema = VERDICT_FORMAT["json_schema"]["schema"]

    for shape in [schema, *schema["$defs"].values()]:
        assert shape["additionalProperties"] is False
        assert set(shape["required"]) == set(shape["properties"])
