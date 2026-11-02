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
from modules.jobs.evidence.retrieval import Retriever
from modules.jobs.workbook_rows.ask import AnswerModel, passages_block
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.decide import RowResult, answer_row
from modules.jobs.workbook_rows.layout import Layout, QuestionRow, find_questions
from modules.jobs.workbook_rows.operations import exception_lines, operations

# A token is about 3.5 characters of English; 3 leaves room for numbers and tables.
CHARS_PER_TOKEN = 3
# What a window of unknown size is taken to be: the floor every agent model meets.
UNKNOWN_WINDOW = 32_768


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
    retriever = Retriever(passages, budget, config.passages_per_question)

    def one(row: QuestionRow) -> RowResult:
        shown = retriever.for_question(f"{row.question} {row.context}")
        return answer_row(
            model, config, row, passages_block(passages, shown), passages, sources
        )

    results = _answer_all(rows, one, max(model.concurrency, 1), on_row, stop)
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
    workers: int,
    on_row: Callable[[int, int], None] | None,
    stop: Callable[[], bool] | None,
) -> list[RowResult]:
    """Rows in sheet order; a stop is checked between questions, never inside a call."""
    results: dict[int, RowResult] = {}
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
                results[pending.pop(future)] = future.result()
                if on_row is not None:
                    on_row(len(results), len(rows))
    if len(results) < len(rows):
        raise FillStoppedError(
            f"Stopped after {len(results)} of {len(rows)} questions."
        )
    return [results[i] for i in range(len(rows))]
