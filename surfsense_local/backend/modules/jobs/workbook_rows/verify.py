"""A second look at a quoted answer: does its quote, on its own, settle the question?

The quote check proves the passage exists; this asks whether it says what the answer
claims. Qwen3.5-9B quoted related but different controls for 8 to 14 CAIQ answers a
run; a narrow question about one quote is easier for a model than the answer was.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from string import Template

from modules.jobs.workbook_rows.ask import AnswerModel
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.layout import QuestionRow

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "missing": {"type": "string"},
    },
    "required": ["supported", "missing"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Verdict:
    supported: bool
    missing: str  # what the quote leaves out, for the exceptions sheet
    input_tokens: int
    output_tokens: int


def verify_answer(
    model: AnswerModel,
    config: JobConfig,
    row: QuestionRow,
    answer: str,
    quote: str,
    source: str,
) -> Verdict:
    """Supported only on a reply that says so: an unreadable one leaves the answer to a person."""
    fields = {
        "question": row.question,
        "context": row.context or "none",
        "answer": answer,
        "quote": quote,
        "source": source,
    }
    prompt = Template(config.verify_prompt).safe_substitute(fields)
    reply = model.ask(prompt, [("user", _claim(fields))], VERIFY_SCHEMA, 0)
    supported, missing = _read(reply.text)
    return Verdict(
        supported, missing, reply.input_tokens or 0, reply.output_tokens or 0
    )


def _claim(fields: dict[str, str]) -> str:
    return (
        f"Question: {fields['question']}\nRow details: {fields['context']}\n"
        f"Answer given: {fields['answer']}\n"
        f'Quote it rests on, from {fields["source"]}: "{fields["quote"]}"'
    )


def _read(text: str) -> tuple[bool, str]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return False, "The check of the quote could not be read."
    try:
        raw = json.loads(text[start : end + 1])
    except ValueError:
        return False, "The check of the quote could not be read."
    supported = raw.get("supported") if isinstance(raw, dict) else None
    if not isinstance(supported, bool):
        return False, "The check of the quote could not be read."
    missing = str(raw.get("missing") or "").strip()
    return supported, re.sub(r"\s+", " ", missing)
