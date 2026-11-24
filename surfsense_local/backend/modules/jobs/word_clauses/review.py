"""The word-clauses runner: each review point checked against the firm's playbook, and the tracked
changes and comments that bring the contract in line with it.

Pure over files and a model: Studio's worker and the eval harness run this same code, so an eval
measures what the app does.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from modules.jobs.asking.answer_all import TURN_ROWS, answer_all
from modules.jobs.asking.model import AnswerModel
from modules.jobs.asking.stopped import FillStoppedError
from modules.jobs.asking.turns import taking_turns
from modules.jobs.asking.window import window_chars
from modules.jobs.evidence.passages import SourceText, passages_of
from modules.jobs.evidence.passages_block import passages_block
from modules.jobs.evidence.retrieval import Embed, Retriever
from modules.jobs.provenance import quote_check
from modules.jobs.word_clauses.ask import SAID, point_prompt
from modules.jobs.word_clauses.config import ClauseConfig, ReviewPoint
from modules.jobs.word_clauses.contract import Contract, read_contract
from modules.jobs.word_clauses.decide import PointResult, decide_point, failed_point
from modules.jobs.word_clauses.operations import counts_of, planned_operations
from modules.jobs.word_clauses.outline import Outline, point_query
from modules.jobs.word_clauses.preflight import SelfCheckFailedError, refusals

# Rounds of trying the operations, each sending what the engine refused to a person; a contract
# settles in one or two.
MAX_ROUNDS = 8


class NoClausesError(Exception):
    """A contract with no text the engine reads, so the run has nothing to review."""


@dataclass
class ReviewResult:
    contract: Contract
    results: list[PointResult]
    operations: list[dict]
    seconds: float
    whole_sources: bool
    whole_contract: bool
    counts: dict[str, int] = field(default_factory=dict)
    # The firm's settings the run used, every one the job declares.
    settings: dict[str, bool] = field(default_factory=dict)

    @property
    def calls(self) -> int:
        return sum(r.calls for r in self.results)

    @property
    def input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.results)

    @property
    def output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.results)

    @property
    def exceptions(self) -> list[list[object]]:
        """Each point left to a person: [paragraph, its text, point, verdict said, why]."""
        rows: list[list[object]] = []
        for result in self.results:
            if result.verdict != "for_person":
                continue
            index = next(
                (
                    i
                    for i in map(self.contract.find, result.paragraphs)
                    if i is not None
                ),
                None,
            )
            clause = self.contract.clauses[index] if index is not None else None
            where = ""
            if clause is not None:
                where = f"{clause.id} ({clause.label})" if clause.label else clause.id
            text = clause.text.strip() if clause is not None else ""
            shown = text if len(text) <= 120 else text[:117] + "..."
            rows.append([where, shown, result.point.title, result.said, result.why])
        return rows


def review_contract(
    contract: Path,
    sources: list[SourceText],
    config: ClauseConfig,
    model: AnswerModel,
    *,
    only: Callable[[ReviewPoint], bool] | None = None,
    on_row: Callable[[int, int], None] | None = None,
    stop: Callable[[], bool] | None = None,
    embed: Embed | None = None,
    checker: AnswerModel | None = None,
    settings: Mapping[str, object] | None = None,
    take_turns: bool = False,
) -> ReviewResult:
    """`checker` makes the second checks, the answering model when None; `settings` are the
    firm's choices for the job, by key. `take_turns` is for a checker that cannot be loaded
    beside the answering model."""
    started = time.monotonic()
    chosen = config.setting_values(settings)
    read = read_contract(contract)
    if not read.clauses:
        # Before any embedding, which takes minutes on a laptop for nothing to review.
        raise NoClausesError("SurfSense found no text in this contract to review.")
    points = [p for p in config.points if only is None or only(p)]
    if on_row is not None:
        on_row(0, len(points))
    passages = passages_of(sources)

    def embedding(texts: list[str], query: bool) -> list[list[float]]:
        # A cancel is honoured between a library's batches; a point's query runs on the point
        # threads, while the worker's cancel reads the run's one database session.
        if not query and stop is not None and stop():
            raise FillStoppedError("Stopped before the first review point.")
        return embed(texts, query)  # type: ignore[misc]

    using = embedding if embed is not None else None
    retriever = Retriever(
        passages,
        window_chars(model.window, config.sources_share, config.max_sources_chars),
        config.passages_per_point,
        embed=using,
    )
    outline = Outline(
        read,
        window_chars(model.window, config.contract_share, config.max_contract_chars),
        config.clauses_per_point,
        using,
    )
    shared = {
        "verdicts": ", ".join(SAID),
        "min_quote_chars": str(config.min_quote_chars),
    }
    if outline.whole:
        shared["outline"] = outline.full
    if retriever.whole:
        shared["passages"] = passages_block(passages, list(range(len(passages))))
    turns, asking, checking = taking_turns(model, checker, take_turns)

    def one(point: ReviewPoint) -> PointResult:
        own = {"point": point.title, "covers": point.covers or point.title}
        if not outline.whole:
            own["outline"] = outline.for_point(point)
        if not retriever.whole:
            shown = retriever.for_question(point_query(point))
            own["passages"] = passages_block(passages, shown)
        prompt = point_prompt(config, shared, own)
        return decide_point(
            asking, config, read, point, prompt, passages, sources, checker=checking
        )

    try:
        results = answer_all(
            points,
            one,
            failed_point,
            TURN_ROWS if turns is not None else max(model.concurrency, 1),
            on_row,
            stop,
            turns,
            named=lambda point: f"review point {point.key}",
            counted="review points",
        )
    finally:
        quote_check.forget()
    operations = _settled(contract, read, results, config, chosen)
    return ReviewResult(
        contract=read,
        results=results,
        operations=operations,
        seconds=round(time.monotonic() - started, 1),
        whole_sources=retriever.whole,
        whole_contract=outline.whole,
        counts=counts_of(results),
        settings=chosen,
    )


def _settled(
    path: Path,
    contract: Contract,
    results: list[PointResult],
    config: ClauseConfig,
    settings: Mapping[str, bool],
) -> list[dict]:
    """Operations the engine applies all of: what it refuses goes to a person, and the rest are
    tried again, until none is refused."""
    dropped: set[tuple[int | None, str]] = set()
    refused: dict = {}
    planned = []
    for _ in range(MAX_ROUNDS):
        planned = planned_operations(contract, results, config, settings, dropped)
        try:
            refused = refusals(path, [p.op for p in planned])
        except SelfCheckFailedError as failed:
            changed = [r for r in results if r.change is not None]
            if not changed:
                raise
            for result in changed:
                result.to_person(
                    "SELF_CHECK_FAILED", f"Word could not make the change: {failed}"
                )
            continue
        if not refused:
            break
        for index, outcome in refused.items():
            planned_op = planned[index]
            if planned_op.role == "change":
                results[planned_op.point].to_person(  # type: ignore[index]
                    f"REFUSED_{outcome.code}",
                    f"Word refused the change: {outcome.message}",
                )
            else:
                dropped.add((planned_op.point, planned_op.role))
    return [p.op for index, p in enumerate(planned) if index not in refused]
