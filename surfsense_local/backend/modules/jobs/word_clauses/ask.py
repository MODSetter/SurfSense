"""One review point to the model under a JSON schema: the contract, the playbook's passages and the
point, with the reply read leniently.

The contract comes first and is the same for every point, so a runtime or provider that reuses a
prompt's start reads it once.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from string import Template

from modules.jobs.asking.model import AnswerModel
from modules.jobs.word_clauses.config import ClauseConfig

# What the model may say of a point. "unclear" leaves it to a person.
SAID = ("meets", "deviates", "missing", "not_covered", "unclear")
KINDS = ("replace", "insert_after", "delete", "none")
# Stands for a point's own words while the shared start of its prompt is measured.
_OWN = "\x00"
_SPELLINGS = {
    "not covered": "not_covered",
    "notcovered": "not_covered",
    "insert": "insert_after",
    "insert_paragraphs": "insert_after",
    "replace_text": "replace",
    "delete_text": "delete",
    "delete_paragraphs": "delete",
}


@dataclass(frozen=True)
class Edit:
    kind: str
    paragraph: str
    old_text: str
    new_text: str


@dataclass(frozen=True)
class Draft:
    said: str
    paragraphs: tuple[str, ...]
    passage: int  # 1-based number of the playbook passage quoted; 0 for none
    quote: str
    edit: Edit
    external: str  # the reason the other side may read
    internal: str  # SurfSense's reasoning, kept in Studio


@dataclass
class Asked:
    """A point's draft with what it cost; `draft` is None when no reply could be read."""

    draft: Draft | None = None
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    replies: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PointPrompt:
    system: str
    first: str
    shared: int  # leading characters of `first` every point repeats
    fields: dict[str, str]


def point_prompt(
    config: ClauseConfig, shared: dict[str, str], own: dict[str, str]
) -> PointPrompt:
    """`shared` fields read the same for every point, `own` ones differ."""
    fields = {**shared, **own}
    first = Template(config.point_prompt).safe_substitute(fields)
    probe = Template(config.point_prompt).safe_substitute(
        {**shared, **dict.fromkeys(own, _OWN)}
    )
    start = probe.find(_OWN)
    return PointPrompt(
        Template(config.system_prompt).safe_substitute(fields),
        first,
        len(first) if start < 0 else start,
        fields,
    )


def point_schema() -> dict:
    # No null-able types and no bounds, which llama.cpp's grammar builder and some structured
    # output engines refuse. Evidence and reasoning come before the verdict they lead to.
    text = {"type": "string"}
    return {
        "type": "object",
        "properties": {
            "paragraphs": {"type": "array", "items": text},
            "playbook_passage": {"type": "integer"},
            "playbook_quote": text,
            "internal_comment": text,
            "verdict": {"type": "string", "enum": list(SAID)},
            "edit": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "paragraph": text,
                    "old_text": text,
                    "new_text": text,
                },
                "required": ["kind", "paragraph", "old_text", "new_text"],
                "additionalProperties": False,
            },
            "external_comment": text,
        },
        "required": [
            "paragraphs",
            "playbook_passage",
            "playbook_quote",
            "internal_comment",
            "verdict",
            "edit",
            "external_comment",
        ],
        "additionalProperties": False,
    }


def ask_point(
    model: AnswerModel,
    config: ClauseConfig,
    prompt: PointPrompt,
    repair: str | None = None,
    earlier: Asked | None = None,
) -> Asked:
    """Ask once, and once more with `repair` when the reply broke a rule the runner checks."""
    turns = [("user", prompt.first)]
    asked = earlier or Asked()
    if earlier is not None and repair is not None:
        ask_again = Template(config.repair_prompt).safe_substitute(
            {**prompt.fields, "problem": repair}
        )
        if earlier.replies[-1].strip():
            turns += [("assistant", earlier.replies[-1]), ("user", ask_again)]
        else:
            # An empty reply cannot be sent back: APIs refuse an empty assistant turn.
            turns = [("user", f"{prompt.first}\n\n{ask_again}")]
    reply = model.ask(prompt.system, turns, point_schema(), prompt.shared)
    asked.calls += 1
    asked.input_tokens += reply.input_tokens or 0
    asked.output_tokens += reply.output_tokens or 0
    asked.replies.append(reply.text)
    asked.draft = parse_draft(reply.text)
    if asked.draft is None and earlier is None:
        return ask_point(
            model,
            config,
            prompt,
            repair="Your reply was not one JSON object with the fields asked for.",
            earlier=asked,
        )
    return asked


def parse_draft(text: str) -> Draft | None:
    """The reply's JSON object, read leniently around it; None when it holds no verdict."""
    body = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", body, re.DOTALL)
    if fenced:
        body = fenced.group(1)
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        raw = json.loads(body[start : end + 1])
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    said = _word(raw.get("verdict"))
    if said not in SAID:
        return None
    edit = raw.get("edit") if isinstance(raw.get("edit"), dict) else {}
    kind = _word(edit.get("kind")) or "none"
    try:
        passage = max(int(raw.get("playbook_passage") or 0), 0)
    except (TypeError, ValueError):
        passage = 0
    listed = raw.get("paragraphs")
    return Draft(
        said=said,
        paragraphs=tuple(
            p
            for p in (
                paragraph_id(item)
                for item in (listed if isinstance(listed, list) else [listed])
            )
            if p
        ),
        passage=passage,
        quote=_text(raw.get("playbook_quote")),
        edit=Edit(
            kind=kind if kind in KINDS else "none",
            paragraph=paragraph_id(edit.get("paragraph")),
            old_text=_text(edit.get("old_text")),
            new_text=_text(edit.get("new_text")),
        ),
        external=_text(raw.get("external_comment")),
        internal=_text(raw.get("internal_comment")),
    )


def paragraph_id(value: object) -> str:
    """ "P12" for any of 12, "12", "p12" or "[P12 | 4.2]"; "" for a clause number such as "4.2",
    which names no paragraph."""
    text = str(value or "").strip()
    found = re.search(r"\bP\s*(\d+)\b", text, re.IGNORECASE) or re.fullmatch(
        r"(\d+)", text
    )
    return f"P{int(found.group(1))}" if found else ""


def _word(value: object) -> str:
    word = str(value or "").strip().casefold().replace("-", "_")
    return _SPELLINGS.get(word, word.replace(" ", "_"))


def _text(value: object) -> str:
    return str(value or "").strip()
