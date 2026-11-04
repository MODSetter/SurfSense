"""The workbook-rows runner: find the questions, answer each from the sources, and say what to write.

Pure over files and a model: Studio's worker and the eval harness run this same code,
so an eval row measures what the app does.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path

from modules.artifacts.revised_copies.engines.excel_inspection import inspect_workbook
from modules.jobs.evidence.passages import SourceText, passages_of
from modules.jobs.evidence.retrieval import Embed, Retriever
from modules.jobs.provenance import quote_check
from modules.jobs.workbook_rows.ask import AnswerModel, ModelReply, passages_block
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.decide import RowResult, answer_row, failed_row
from modules.jobs.workbook_rows.layout import Layout, QuestionRow, find_questions
from modules.jobs.workbook_rows.operations import exception_lines, operations

logger = logging.getLogger(__name__)

# A token is about 3.5 characters of English; 3 leaves room for numbers and tables.
CHARS_PER_TOKEN = 3
# What a window of unknown size is taken to be: the floor every agent model meets.
UNKNOWN_WINDOW = 32_768
# Rows whose calls may fail outright before the run itself is taken to be failing, and
# only while they stay under a tenth of the questions.
MAX_FAILED_ROWS = 3
# Questions under way at once while two models take turns, so each turn has many calls.
TURN_ROWS = 128
# How often a run whose questions are all under way checks for a cancel.
STOP_POLL_SECONDS = 2.0


class FillStoppedError(Exception):
    """The run was cancelled between questions."""


class Turns:
    """Two models that cannot be loaded at once take turns. A call to the one out of turn
    waits; the turn passes when the one in turn has no call running or waiting and no question
    is still working towards one. The local runtime holds one model at a time, so answering
    with one model and checking with another would otherwise load a model twice a question."""

    def __init__(self, slots: int) -> None:
        self._slots = max(slots, 1)
        self._turn: str | None = None
        self._running = 0
        self._waiting: Counter[str] = Counter()
        # Questions under way and not waiting for a turn: between calls, or in one.
        self._working = 0
        self._halted = False
        self._lock = threading.Lock()
        # One condition a side, so a freed slot wakes only calls that may take it.
        self._ready: dict[str, threading.Condition] = {}

    def started(self) -> None:
        with self._lock:
            self._working += 1

    def finished(self) -> None:
        with self._lock:
            self._working -= 1
            self._pass()

    def halt(self) -> None:
        """Every call not yet running raises FillStoppedError from now on."""
        with self._lock:
            self._halted = True
            for ready in self._ready.values():
                ready.notify_all()

    def ask(self, side: str, call: Callable[[], ModelReply]) -> ModelReply:
        with self._lock:
            ready = self._ready.setdefault(side, threading.Condition(self._lock))
            self._working -= 1
            self._waiting[side] += 1
            self._pass()
            while not self._halted and not (
                self._turn == side and self._running < self._slots
            ):
                ready.wait()
            self._waiting[side] -= 1
            self._working += 1
            if self._halted:
                raise FillStoppedError("Stopped while questions were under way.")
            self._running += 1
        try:
            return call()
        finally:
            with self._lock:
                self._running -= 1
                self._pass()

    def _pass(self) -> None:
        """Held with the lock. The turn passes to a side that waits once nothing more can come
        of the side in turn; then as many calls of the side in turn wake as there are slots."""
        if self._turn is None or not (self._working or self._waiting[self._turn]):
            waiting = [side for side, count in self._waiting.items() if count]
            if waiting:
                self._turn = waiting[0]
        if self._turn is not None and self._running < self._slots:
            self._ready[self._turn].notify(self._slots - self._running)


class TurnModel:
    """A model whose calls wait for its side's turn."""

    def __init__(self, model: AnswerModel, turns: Turns, side: str) -> None:
        self._model = model
        self._turns = turns
        self._side = side
        self.name = model.name
        self.window = model.window
        self.concurrency = model.concurrency

    def ask(
        self, system: str, turns: list[tuple[str, str]], schema: dict, shared: int
    ) -> ModelReply:
        return self._turns.ask(
            self._side, lambda: self._model.ask(system, turns, schema, shared)
        )


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

    turns = Turns(model.concurrency) if take_turns and checker is not None else None
    asking, checking = (
        (model, checker)
        if turns is None
        else (TurnModel(model, turns, "answer"), TurnModel(checker, turns, "check"))  # type: ignore[arg-type]
    )

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
        results = _answer_all(
            rows,
            one,
            lambda row, error: failed_row(config, row, error),
            TURN_ROWS if turns is not None else max(model.concurrency, 1),
            on_row,
            stop,
            turns,
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


def _answer_all(
    rows: list[QuestionRow],
    one: Callable[[QuestionRow], RowResult],
    failed: Callable[[QuestionRow, Exception], RowResult],
    workers: int,
    on_row: Callable[[int, int], None] | None,
    stop: Callable[[], bool] | None,
    turns: Turns | None = None,
) -> list[RowResult]:
    """Rows in sheet order. A stop is checked on this thread, which alone may read what it
    reads, between questions and while they are under way; a call already made is let finish."""
    results: dict[int, RowResult] = {}
    failures = 0

    def taking_turns(row: QuestionRow) -> RowResult:
        try:
            return one(row)
        finally:
            turns.finished()  # type: ignore[union-attr]

    def stopped() -> bool:
        if stop is None or not stop():
            return False
        if turns is not None:
            turns.halt()  # questions under way raise at their next call
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending: dict[Future, int] = {}
        queue = list(enumerate(rows))
        try:
            while queue or pending:
                while queue and len(pending) < workers:
                    if stopped():
                        queue.clear()
                        break
                    index, row = queue.pop(0)
                    if turns is None:
                        pending[pool.submit(one, row)] = index
                    else:
                        # Counted before its thread starts, so no turn passes while it waits.
                        turns.started()
                        pending[pool.submit(taking_turns, row)] = index
                if not pending:
                    break
                done, _ = wait(
                    pending, timeout=STOP_POLL_SECONDS, return_when=FIRST_COMPLETED
                )
                if not done or turns is not None:
                    # Taking turns, every question is under way at once: the stop is read
                    # here, not only before a question starts.
                    if stopped():
                        queue.clear()
                    if not done:
                        continue
                for future in done:
                    index = pending.pop(future)
                    try:
                        results[index] = future.result()
                    except FillStoppedError:
                        raise
                    except Exception as error:
                        # One question's call failing goes to a person; many failing is the
                        # connection itself, which the run reports instead of a sheet of blanks.
                        logger.warning(
                            "question in %s!%s failed",
                            rows[index].sheet,
                            rows[index].answer_cell,
                            exc_info=error,
                        )
                        failures += 1
                        every = failures == len(rows)
                        if every or (
                            failures >= MAX_FAILED_ROWS and failures * 10 > len(rows)
                        ):
                            raise
                        results[index] = failed(rows[index], error)
                    if on_row is not None:
                        on_row(len(results), len(rows))
        except BaseException:
            # Questions waiting for a turn would otherwise run on to the end of theirs.
            if turns is not None:
                turns.halt()
            raise
    if len(results) < len(rows):
        raise FillStoppedError(
            f"Stopped after {len(results)} of {len(rows)} questions."
        )
    return [results[i] for i in range(len(rows))]
