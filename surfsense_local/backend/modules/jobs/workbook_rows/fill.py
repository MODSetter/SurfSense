"""The workbook-rows runner: find the questions, answer each from the sources, and say what to write.

Pure over files and a model: Studio's worker and the eval harness run this same code,
so an eval row measures what the app does.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path

from modules.artifacts.revised_copies.engines.excel_inspection import inspect_workbook
from modules.jobs.evidence.passages import SourceText, passages_of
from modules.jobs.evidence.retrieval import Embed, Retriever
from modules.jobs.provenance import quote_check
from modules.jobs.workbook_rows.ask import AnswerModel, passages_block
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.decide import RowResult, answer_row, failed_row
from modules.jobs.workbook_rows.layout import Layout, QuestionRow, find_questions
from modules.jobs.workbook_rows.operations import exception_lines, operations

# A token is about 3.5 characters of English; 3 leaves room for numbers and tables.
CHARS_PER_TOKEN = 3
# What a window of unknown size is taken to be: the floor every agent model meets.
UNKNOWN_WINDOW = 32_768
# Rows whose calls may fail outright before the run itself is taken to be failing, and
# only while they stay under a tenth of the questions.
MAX_FAILED_ROWS = 3


class FillStoppedError(Exception):
    """The run was cancelled between questions."""


@dataclass
class FillResult:
    layout: Layout
    results: list[RowResult]
    operations: list[dict]
    whole_sources: bool
    seconds: float
    counts: dict[str, int] = field(default_factory=dict)

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
) -> FillResult:
    started = time.monotonic()
    facts = inspect_workbook(workbook)
    layout = find_questions(facts, config.layout)
    rows = [row for row in layout.rows if only is None or only(row)]
    passages = passages_of(sources)
    budget = min(
        int(
            (model.window or UNKNOWN_WINDOW)
            * config.whole_sources_share
            * CHARS_PER_TOKEN
        ),
        config.max_whole_chars,
    )

    def embedding(texts: list[str], query: bool) -> list[list[float]]:
        # Embedding a library takes minutes on a laptop: a cancel is honoured between batches.
        if stop is not None and stop():
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

    def one(row: QuestionRow) -> RowResult:
        # The question alone: CAIQ's row repeats its control's boilerplate, which drowned
        # the words that tell one question from the next (deciding passages 22 of 34, not 20).
        shown = retriever.for_question(row.question)
        block = passages_block(
            passages, shown, retriever.pinned, config.standing_labels
        )
        result = answer_row(model, config, row, block, passages, sources)
        if not retriever.whole:
            # What the question saw, as the model numbered it, for a person tracing a miss.
            result.shown = [
                index + 1 for index in dict.fromkeys([*retriever.pinned, *shown])
            ]
        return result

    try:
        results = _answer_all(
            rows,
            one,
            lambda row, error: failed_row(config, row, error),
            max(model.concurrency, 1),
            on_row,
            stop,
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
    )


def _answer_all(
    rows: list[QuestionRow],
    one: Callable[[QuestionRow], RowResult],
    failed: Callable[[QuestionRow, Exception], RowResult],
    workers: int,
    on_row: Callable[[int, int], None] | None,
    stop: Callable[[], bool] | None,
) -> list[RowResult]:
    """Rows in sheet order; a stop is checked between questions, never inside a call."""
    results: dict[int, RowResult] = {}
    failures = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending: dict[Future, int] = {}
        queue = list(enumerate(rows))
        while queue or pending:
            while queue and len(pending) < workers:
                if stop is not None and stop():
                    queue.clear()
                    break
                index, row = queue.pop(0)
                pending[pool.submit(one, row)] = index
            if not pending:
                break
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index = pending.pop(future)
                try:
                    results[index] = future.result()
                except FillStoppedError:
                    raise
                except Exception as error:
                    # One question's call failing goes to a person; many failing is the
                    # connection itself, which the run reports instead of a sheet of blanks.
                    failures += 1
                    every = failures == len(rows)
                    if every or (
                        failures >= MAX_FAILED_ROWS and failures * 10 > len(rows)
                    ):
                        raise
                    results[index] = failed(rows[index], error)
                if on_row is not None:
                    on_row(len(results), len(rows))
    if len(results) < len(rows):
        raise FillStoppedError(
            f"Stopped after {len(results)} of {len(rows)} questions."
        )
    return [results[i] for i in range(len(rows))]
