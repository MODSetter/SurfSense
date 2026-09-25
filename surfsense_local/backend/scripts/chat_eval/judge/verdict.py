"""One verdict: what the judge is shown about a reply, and what is kept of its answer."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from modules.llm.providers.types import Message

_RUBRIC = Path(__file__).with_name("verdict.md").read_text(encoding="utf-8")
# Recorded with every verdict: an edited rubric is a different judge.
RUBRIC_VERSION = hashlib.sha256(_RUBRIC.encode()).hexdigest()[:8]


class Failure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: Literal["grounded", "complete", "citations", "gaps", "language"]
    quote: str
    problem: str
    cause: Literal[
        "prompt_instruction",
        "prompt_example",
        "grounding_format",
        "model_capacity",
        "case",
    ]
    fix: str


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grounded: bool
    complete: bool
    citations: bool
    # None when a passage holds the answer, so there was no gap to admit.
    gaps: bool | None
    language: bool
    failures: list[Failure]
    summary: str


# Strict mode holds the judge to the schema where its provider supports it;
# verdict_record checks every reply either way.
VERDICT_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "verdict",
        "strict": True,
        "schema": Verdict.model_json_schema(),
    },
}


def verdict_request(record: dict) -> list[Message]:
    """What the model saw and did, and what it should have done."""
    shown = "\n".join(
        f'<message role="{message["role"]}">\n{message["content"]}\n</message>'
        for message in record["messages"]
    )
    return [
        Message("system", _RUBRIC),
        Message(
            "user",
            f"Model: {record['model']}, on the {record['tier']} prompt tier\n\n"
            f"<model_input>\n{shown}\n</model_input>\n\n"
            f"<model_reasoning>\n{record['reasoning'] or '(none)'}\n</model_reasoning>\n\n"
            f"<model_answer>\n{record['answer']}\n</model_answer>\n\n"
            f"<answer_key>\n{_answer_key(record['answer_key'])}\n</answer_key>\n\n"
            f"<rule_checks>\n{json.dumps(record['score'])}\n</rule_checks>",
        ),
    ]


def verdict_record(record: dict, reply: str, judge: str) -> dict:
    """The judge's reply checked against the schema, filed under the reply it judged."""
    kept = {
        "case": record["case"],
        "repeat": record["repeat"],
        "judge": judge,
        "rubric": RUBRIC_VERSION,
    }
    try:
        return {**kept, "verdict": Verdict.model_validate_json(reply).model_dump()}
    except ValidationError as error:
        return {**kept, "error": str(error)}


def _answer_key(key: dict) -> str:
    lines = [
        "Passages that hold the answer: "
        + ", ".join(f"[{n}]" for n in key["supporting"])
        if key["supporting"]
        else "No passage holds the answer."
    ]
    if key["facts"]:
        lines.append(f"A correct answer states: {', '.join(key['facts'])}")
    return "\n".join(lines)
