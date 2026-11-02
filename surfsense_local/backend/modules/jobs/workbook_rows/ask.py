"""One question to the model under a JSON schema: the passages, the row, and what it must reply.

The passages come first and stay the same from row to row when they all fit, so a runtime
or provider that reuses a prompt's start reads them once.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from string import Template
from typing import Protocol

from modules.jobs.evidence.passages import Passage
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.layout import QuestionRow

CONFIDENCE = ("high", "medium", "low")
# Enough for a quote and a two-sentence comment; a reply this long has lost its way.
MAX_REPLY_TOKENS = 700


@dataclass(frozen=True)
class ModelReply:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class AnswerModel(Protocol):
    """The model a job runs on; the app's selected model in Studio, a fixed one in an eval.

    `shared` is how many leading characters of the first turn every question repeats:
    a provider that caches by marked blocks marks that much.
    """

    name: str
    window: int | None  # tokens it reads at once; None when it is not known
    concurrency: int  # questions it may take at once

    def ask(
        self, system: str, turns: list[tuple[str, str]], schema: dict, shared: int
    ) -> ModelReply: ...


@dataclass(frozen=True)
class Quoted:
    passage: int  # 1-based passage number as shown; 0 for none
    quote: str


@dataclass(frozen=True)
class Draft:
    # One quote per part of the question that a different passage settles, first the main one.
    quotes: tuple[Quoted, ...]
    answer: str
    comment: str
    confidence: str


@dataclass
class Asked:
    """A row's draft with what it cost; `draft` is None when no reply could be read."""

    draft: Draft | None
    calls: int
    input_tokens: int
    output_tokens: int
    replies: list[str]


def answer_schema(config: JobConfig) -> dict:
    # No null-able types: llama.cpp's grammar builder refuses those. No bounds on numbers or
    # lists either, which not every structured-output engine takes: the runner keeps the first
    # `max_quotes` quotes itself.
    return {
        "type": "object",
        "properties": {
            "quotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "passage": {"type": "integer"},
                        "quote": {"type": "string"},
                    },
                    "required": ["passage", "quote"],
                    "additionalProperties": False,
                },
            },
            "answer": {"type": "string", "enum": [c.answer for c in config.answers]},
            "comment": {"type": "string"},
            "confidence": {"type": "string", "enum": list(CONFIDENCE)},
        },
        "required": ["quotes", "answer", "comment", "confidence"],
        "additionalProperties": False,
    }


def passages_block(
    passages: list[Passage],
    shown: list[int],
    standing: list[int] | None = None,
    labels: tuple[str, str] = ("", ""),
) -> str:
    """The passages as the model reads them, in the sources' order; with the pack's labels,
    those every question is shown come first under theirs, so the model knows which apply
    to all the firm's policies."""
    pinned = [i for i in standing or () if i in shown]
    if not pinned or not any(labels):
        return _listed(passages, shown)
    own = [i for i in shown if i not in pinned]
    parts = [labels[0], _listed(passages, pinned)]
    if own:
        parts += [labels[1], _listed(passages, own)]
    return "\n\n".join(part for part in parts if part)


def _listed(passages: list[Passage], shown: list[int]) -> str:
    blocks = []
    for index in shown:
        passage = passages[index]
        where = f" — {passage.section}" if passage.section else ""
        blocks.append(
            f"[{index + 1}] {passage.title}{where} (lines {passage.first_line}-{passage.last_line})\n"
            f"{passage.text}"
        )
    return "\n\n".join(blocks)


def ask_row(
    model: AnswerModel,
    config: JobConfig,
    row: QuestionRow,
    block: str,
    repair: str | None = None,
    earlier: Asked | None = None,
) -> Asked:
    """Ask once, and once more with `repair` when the first reply broke a rule the app checks."""
    fields = _fields(config, row, block)
    system = Template(config.system_prompt).safe_substitute(fields)
    first = Template(config.question_prompt).safe_substitute(fields)
    turns = [("user", first)]
    shared = first.find(block) + len(block) if block and block in first else 0
    asked = earlier or Asked(None, 0, 0, 0, [])
    if earlier is not None and repair is not None:
        turns += [
            ("assistant", earlier.replies[-1]),
            (
                "user",
                Template(config.repair_prompt).safe_substitute(
                    {**fields, "problem": repair}
                ),
            ),
        ]
    reply = model.ask(system, turns, answer_schema(config), shared)
    asked.calls += 1
    asked.input_tokens += reply.input_tokens or 0
    asked.output_tokens += reply.output_tokens or 0
    asked.replies.append(reply.text)
    asked.draft = parse_draft(reply.text, config)
    if asked.draft is None and earlier is None:
        return ask_row(
            model,
            config,
            row,
            block,
            repair="Your reply was not one JSON object with the fields asked for.",
            earlier=asked,
        )
    return asked


def parse_draft(text: str, config: JobConfig) -> Draft | None:
    """The reply's JSON object, read leniently around it; None when it holds no usable answer."""
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
    answer = str(raw.get("answer", "")).strip()
    by_folded = {c.answer.casefold(): c.answer for c in config.answers}
    if answer.casefold() not in by_folded:
        return None
    confidence = str(raw.get("confidence", "")).strip().casefold()
    return Draft(
        quotes=_quotes(raw.get("quotes"))[: config.max_quotes],
        answer=by_folded[answer.casefold()],
        comment=str(raw.get("comment") or "").strip(),
        confidence=confidence if confidence in CONFIDENCE else "low",
    )


def _quotes(raw: object) -> tuple[Quoted, ...]:
    """The reply's quotes that hold any text, in its order."""
    found = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote") or "").strip()
        if not quote:
            continue
        try:
            passage = int(item.get("passage") or 0)
        except (TypeError, ValueError):
            passage = 0
        found.append(Quoted(max(passage, 0), quote))
    return tuple(found)


def _fields(config: JobConfig, row: QuestionRow, block: str) -> dict[str, str]:
    return {
        "answers": ", ".join(c.answer for c in config.answers),
        "fallback": config.fallback.answer,
        "passages": block,
        "question": row.question,
        "context": row.context or "none",
        "sheet": row.sheet,
        "cell": row.answer_cell,
        "allowed": ", ".join(row.allowed) if row.allowed else "free text",
        "min_quote_chars": str(config.min_quote_chars),
        "max_quotes": str(config.max_quotes),
    }
