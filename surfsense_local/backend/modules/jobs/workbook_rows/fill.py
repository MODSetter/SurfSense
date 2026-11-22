"""The workbook-rows runner: find the questions, answer each from the sources, and say what to write.

Pure over files and a model: Studio's worker and the eval harness run this same code,
so an eval row measures what the app does.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from modules.artifacts.revised_copies.engines.excel_inspection import inspect_workbook
from modules.jobs.asking.answer_all import TURN_ROWS, answer_all
from modules.jobs.asking.model import AnswerModel
from modules.jobs.asking.stopped import FillStoppedError as FillStoppedError
from modules.jobs.asking.turns import taking_turns
from modules.jobs.asking.window import window_chars
from modules.jobs.evidence.passages import SourceText, passages_of
from modules.jobs.evidence.passages_block import passages_block
from modules.jobs.evidence.retrieval import Embed, Retriever
from modules.jobs.provenance import quote_check
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.decide import RowResult, answer_row, failed_row
from modules.jobs.workbook_rows.layout import Layout, QuestionRow, find_questions
from modules.jobs.workbook_rows.operations import exception_lines, operations


class NoQuestionsError(Exception):
    """A workbook in which no question was found, so the run has nothing to answer."""


@dataclass
class FillResult:
    layout: Layout
    results: list[RowResult]
    operations: list[dict]
    whole_sources: bool
    seconds: float
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
        return exception_lines(self.results, self.layout.skipped)


def fill_workbook(
    workbook: Path,
    sources: list[SourceText],
    config: JobConfig,
    model: AnswerModel,
    *,
    only: Callable[[QuestionRow], bool] | None = None,
    on_row: Callable[[int, int], None] | None = None,
    stop: Callable[[], bool] | None = None,
    embed: Embed | None = None,
    checker: AnswerModel | None = None,
    settings: Mapping[str, object] | None = None,
    take_turns: bool = False,
) -> FillResult:
    """`checker` makes the second checks, the answering model when None; `settings` are the
    firm's choices for the job, by key, each at its default when left out. `take_turns` is for
    a checker that cannot be loaded beside the answering model."""
    started = time.monotonic()
    chosen = config.setting_values(settings)
    facts = inspect_workbook(workbook)
    layout = find_questions(facts, config.layout)
    if not layout.rows:
        # Before any embedding, which takes minutes on a laptop for nothing to answer.
        raise NoQuestionsError(
            "SurfSense found no questions in this workbook. It needs a column of "
            "questions and a column for answers, or answer dropdowns."
        )
    rows = [row for row in layout.rows if only is None or only(row)]
    if on_row is not None:
        # The total, while the sources are still being read for the first question.
        on_row(0, len(rows))
    passages = passages_of(sources)
    budget = window_chars(
        model.window, config.whole_sources_share, config.max_whole_chars
    )

    def embedding(texts: list[str], query: bool) -> list[list[float]]:
        # Embedding a library takes minutes on a laptop: a cancel is honoured between its
        # batches. Not for a question's query, which runs on the question threads, while the
        # worker's cancel reads the run's one database session.
        if not query and stop is not None and stop():
            raise FillStoppedError("Stopped before the first question.")
        return embed(texts, query)  # type: ignore[misc]

    retriever = Retriever(
        passages,
        budget,
        config.passages_per_question,
        embed=embedding if embed is not None else None,
        standing=config.standing_queries,
        per_standing=config.standing_per_query,
    )

    turns, asking, checking = taking_turns(model, checker, take_turns)

    def one(row: QuestionRow) -> RowResult:
        # The question alone: CAIQ's row repeats its control's boilerplate, which drowned
        # the words that tell one question from the next (deciding passages 22 of 34, not 20).
        shown = retriever.for_question(row.question)
        block = passages_block(
            passages, shown, retriever.pinned, config.standing_labels
        )
        result = answer_row(
            asking,
            config,
            row,
            block,
            passages,
            sources,
            checker=checking,
            settings=chosen,
        )
        if not retriever.whole:
            # What the question saw, as the model numbered it, for a person tracing a miss.
            result.shown = [
                index + 1 for index in dict.fromkeys([*retriever.pinned, *shown])
            ]
        return result

    try:
        results = answer_all(
            rows,
            one,
            lambda row, error: failed_row(config, row, error),
            TURN_ROWS if turns is not None else max(model.concurrency, 1),
            on_row,
            stop,
            turns,
            named=lambda row: f"question in {row.sheet}!{row.answer_cell}",
        )
    finally:
        quote_check.forget()
    ops = operations(results, layout.skipped, config, [s.name for s in facts.sheets])
    counts = Counter(r.answer for r in results)
    counts["blank"] = sum(1 for r in results if r.written is None)
    counts["skipped"] = len(layout.skipped)
    return FillResult(
        layout=layout,
        results=results,
        operations=ops,
        whole_sources=retriever.whole,
        seconds=round(time.monotonic() - started, 1),
        counts=dict(counts),
        settings=chosen,
    )
