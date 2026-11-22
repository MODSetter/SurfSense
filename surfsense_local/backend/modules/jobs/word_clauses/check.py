"""A second look at a proposed change: does the firm's quoted position call for it?

The quote check proves the position is in the playbook; this asks whether it says what the change
claims, a narrower question than the review was.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from string import Template

from modules.jobs.asking.model import AnswerModel
from modules.jobs.word_clauses.config import ReviewPoint

CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "missing": {"type": "string"},
    },
    "required": ["supported", "missing"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Checked:
    supported: bool
    missing: str  # why not, for the person who takes it over
    input_tokens: int
    output_tokens: int


def check_change(
    model: AnswerModel,
    prompt: str,
    point: ReviewPoint,
    position: tuple[str, str],
    clause: str,
    change: str,
) -> Checked:
    """Supported only on a reply that says so. `position` is the playbook's (source, quote);
    `change` says in a sentence what the edit does to `clause`."""
    system = Template(prompt).safe_substitute(point=point.title, covers=point.covers)
    source, quote = position
    claim = (
        f"Review point: {point.title} ({point.covers})\n"
        f'The firm\'s playbook, in {source}: "{quote}"\n'
        f'The contract\'s clause: "{clause}"\n'
        f"Proposed change: {change}"
    )
    reply = model.ask(system, [("user", claim)], CHECK_SCHEMA, 0)
    supported, missing = _read(reply.text)
    return Checked(
        supported, missing, reply.input_tokens or 0, reply.output_tokens or 0
    )


def _read(text: str) -> tuple[bool, str]:
    start, end = text.find("{"), text.rfind("}")
    unreadable = False, "The second check could not be read."
    if start < 0 or end <= start:
        return unreadable
    try:
        raw = json.loads(text[start : end + 1])
    except ValueError:
        return unreadable
    supported = raw.get("supported") if isinstance(raw, dict) else None
    if not isinstance(supported, bool):
        return unreadable
    return supported, re.sub(r"\s+", " ", str(raw.get("missing") or "")).strip()
