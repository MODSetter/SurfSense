"""A second look at a quoted answer: are its quotes, together, evidence for it?

The quote check proves each passage exists; this asks whether they say what the answer
claims. Qwen3.5-9B quoted related but different controls for 8 to 14 CAIQ answers a
run; a narrow question about a few quotes is easier for a model than the answer was.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from string import Template

from modules.jobs.workbook_rows.ask import AnswerModel
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.layout import QuestionRow

# A verdict alone: asking the check to first write out what the question and the quotes are
# about made it refuse more, right answers too (Haiku's CAIQ dev rows fell from 77% to 61%).
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
    missing: str  # what the quotes leave out, for the exceptions sheet
    input_tokens: int
    output_tokens: int


def verify_answer(
    model: AnswerModel,
    config: JobConfig,
    row: QuestionRow,
    answer: str,
    quotes: list[tuple[str, str]],
) -> Verdict:
    """Supported only on a reply that says so: an unreadable one leaves the answer to a person.

    `quotes` are (source title, quote) pairs, each already found in its source.
    """
    fields = {
        "question": row.question,
        "context": row.context or "none",
        "answer": answer,
    }
    prompt = Template(config.verify_prompt).safe_substitute(fields)
    reply = model.ask(prompt, [("user", _claim(fields, quotes))], VERIFY_SCHEMA, 0)
    supported, missing = _read(reply.text)
    return Verdict(
        supported, missing, reply.input_tokens or 0, reply.output_tokens or 0
    )


def _claim(fields: dict[str, str], quotes: list[tuple[str, str]]) -> str:
    claim = (
        f"Question: {fields['question']}\n"
        f"Row details (where the question sits, not part of it): {fields['context']}\n"
        f"Answer given: {fields['answer']}\n"
    )
    if len(quotes) == 1:
        source, quote = quotes[0]
        return claim + f'Quote it rests on, from {source}: "{quote}"'
    listed = "\n".join(
        f'{number}. From {source}: "{quote}"'
        for number, (source, quote) in enumerate(quotes, start=1)
    )
    return claim + f"Quotes it rests on:\n{listed}"


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
