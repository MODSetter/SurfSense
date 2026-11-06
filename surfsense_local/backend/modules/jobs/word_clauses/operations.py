"""The operations a review makes, in document order: its summary, each change with its comments, and
a note on each clause left to a person. Every anchor is one the engine finds once.

Each operation quotes the contract as it reads after the ones before it. Comments and inserted
paragraphs leave a clause's text as it was, so they come before the edits to that clause's text.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from string import Template

from modules.jobs.word_clauses.config import ClauseConfig
from modules.jobs.word_clauses.contract import Contract
from modules.jobs.word_clauses.decide import PointResult
from modules.jobs.word_clauses.placement import unique_anchor

VERDICTS = ("changed", "meets", "not_covered", "for_person")


@dataclass(frozen=True)
class Planned:
    op: dict
    point: int | None  # index into the results; None for the summary
    role: str  # "summary", "note", "change" or "person"
    order: tuple[
        int, int, int
    ]  # clause, then text left alone before text changed, then position


def planned_operations(
    contract: Contract,
    results: list[PointResult],
    config: ClauseConfig,
    settings: Mapping[str, bool],
    dropped: set[tuple[int | None, str]],
) -> list[Planned]:
    """`dropped` names the (point, role) comments the engine refused before, and the clauses a
    refused summary sat on as (None, "summary <clause>"). A change no anchor can place goes to
    a person here."""
    clauses = [c.text for c in contract.clauses]
    added = {
        number: r.change.new_text
        for number, r in enumerate(results)
        if r.change is not None and r.change.new_text
    }
    texts = clauses + list(added.values())
    explained = settings.get("external_comments", True)
    planned: list[Planned] = []
    for number, result in enumerate(results):
        if result.change is not None:
            # A change's quote is found before its own text goes in; every other change's
            # text may read by then.
            others = clauses + [text for n, text in added.items() if n != number]
            planned += _changed(
                contract, result, number, others, config, explained, dropped
            )
        elif result.verdict == "for_person" and (number, "person") not in dropped:
            planned += _person(contract, result, number, texts, config)
    summary = _summary(contract, results, texts, config, dropped)
    return ([summary] if summary else []) + sorted(planned, key=lambda p: p.order)


def counts_of(results: list[PointResult]) -> dict[str, int]:
    counted = Counter(r.verdict for r in results)
    return {**{v: counted.get(v, 0) for v in VERDICTS}, "skipped": 0}


def _changed(
    contract: Contract,
    result: PointResult,
    number: int,
    texts: list[str],
    config: ClauseConfig,
    explained: bool,
    dropped: set[tuple[int | None, str]],
) -> list[Planned]:
    change = result.change
    assert change is not None
    clause = contract.clauses[change.clause]
    if change.kind == "insert_after":
        span = unique_anchor(clause, texts)
    else:
        span = unique_anchor(clause, texts, change.start, change.end)
    if span is None:
        result.to_person("ANCHOR_NOT_UNIQUE")
        return _person(contract, result, number, texts, config)
    start, end = span
    quote = clause.text[start:end]
    if change.kind == "insert_after":
        op: dict = {"op": "insert_paragraphs", "quote": quote, "text": change.new_text}
        rank = 0
    elif (
        change.kind == "delete"
        and not clause.text[: change.start].strip()
        and not (clause.text[change.end :].strip())
    ):
        op = {"op": "delete_paragraphs", "quote": quote}
        rank = 1
    else:
        kept = (
            clause.text[start : change.start]
            + change.new_text
            + clause.text[change.end : end]
        )
        op = {
            "op": "replace_text",
            "quote": quote,
            "text": re.sub(r" {2,}", " ", kept).strip(),
        }
        rank = 1
    note = _filled(config, "note", result, note=result.internal)
    found: list[Planned] = []
    if explained and result.external:
        op.update(comment=result.external, internal=False)
        if (number, "note") not in dropped:
            # Before the change, while the words it sits on still read.
            found.append(
                Planned(
                    {
                        "op": "add_comment",
                        "quote": quote,
                        "text": note,
                        "internal": True,
                    },
                    number,
                    "note",
                    (change.clause, 0, start),
                )
            )
    else:
        op.update(comment=note, internal=True)
    found.append(Planned(op, number, "change", (change.clause, rank, start)))
    return found


def _person(
    contract: Contract,
    result: PointResult,
    number: int,
    texts: list[str],
    config: ClauseConfig,
) -> list[Planned]:
    """A note on the first paragraph the model located, when it located one."""
    for clause_id in result.paragraphs:
        index = contract.find(clause_id)
        if index is None:
            continue
        clause = contract.clauses[index]
        span = unique_anchor(clause, texts)
        if span is None:
            continue
        text = _filled(config, "person", result, why=result.why)
        op = {
            "op": "add_comment",
            "quote": clause.text[span[0] : span[1]],
            "text": text,
            "internal": True,
        }
        return [Planned(op, number, "person", (index, 0, span[0]))]
    return []


def _summary(
    contract: Contract,
    results: list[PointResult],
    texts: list[str],
    config: ClauseConfig,
    dropped: set[tuple[int | None, str]],
) -> Planned | None:
    """One internal comment on the first clause it can sit on: a review that changes nothing
    still saves a version, and the version says what the review found."""
    counts = counts_of(results)
    text = Template(config.templates["summary"]).safe_substitute(
        points=len(results), **{k: counts[k] for k in VERDICTS}
    )
    for index, clause in enumerate(contract.clauses):
        if (None, f"summary {index}") in dropped:
            continue
        span = unique_anchor(clause, texts)
        if span is not None:
            quote = clause.text[span[0] : span[1]]
            op = {"op": "add_comment", "quote": quote, "text": text, "internal": True}
            return Planned(op, None, f"summary {index}", (-1, 0, 0))
    return None


def _filled(
    config: ClauseConfig, template: str, result: PointResult, **fields: str
) -> str:
    return (
        Template(config.templates[template])
        .safe_substitute(
            title=result.point.title,
            source=result.source,
            section=result.section,
            quote=result.quote,
            **fields,
        )
        .strip()
    )
