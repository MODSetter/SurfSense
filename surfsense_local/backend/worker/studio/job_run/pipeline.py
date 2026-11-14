"""A job run's answers, worked out before its revised copy is made: the pack's runner over the
run's file and its sources, on the model the user selected, checked on the firm's checker model
when it chose one, with the firm's settings as they were when the run started.

The write lock is let go while the model answers, which takes minutes; the revise
engine then writes the answers as it writes any other revised copy.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from modules.agent.model_window import selected_model_window
from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.engines.package import PackageRefusedError
from modules.artifacts.revised_copies.revision import REVISION_KEY, revision_of
from modules.documents.models import Document
from modules.documents.original_file import original_path
from modules.embedding import encoder
from modules.embedding.active import active_index
from modules.jobs.asking.model import ModelReply
from modules.jobs.evidence.passages import SourceText
from modules.jobs.evidence.retrieval import Embed
from modules.jobs.evidence.vectors import remembered
from modules.jobs.packs.access import job_access
from modules.jobs.packs.installed import find_job
from modules.jobs.runners import runner_of
from modules.jobs.runs.record import JOB_RUN_KEY, PROGRESS_KEY, job_run_of
from modules.jobs.settings.service import (
    CHECKER_GONE,
    JobSettingsRefusedError,
    check_checker,
)
from modules.jobs.word_clauses.report import RUNNER as CLAUSES_RUNNER
from modules.jobs.word_clauses.report import report_of as review_report
from modules.jobs.word_clauses.review import NoClausesError, review_contract
from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.fill import FillResult, NoQuestionsError, fill_workbook
from modules.jobs.workbook_rows.operations import confirmation, sheet_lines
from modules.llm.model_route.api_address import ApiNotRunningError, api_url
from modules.llm.model_route.client import RoutedGenerator, resolve_routed_generation
from modules.llm.model_route.schemas import ModelRef
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel as ModelChoice
from modules.llm.providers import llamacpp
from modules.llm.providers.stream_deadline import StreamTimeoutError
from modules.llm.providers.types import Message
from modules.llm.resolution import ModelResolutionError, ResolvedGeneration
from worker.studio.job_run.progress import RunProgress, write_progress
from worker.studio.shared.generate import complete

logger = logging.getLogger(__name__)

# Questions a remote model takes at once; a local runtime has one slot.
REMOTE_AT_ONCE = 4
# Room for a thinking model's reasoning before its answer: a remote connection does not
# turn thinking off, and Qwen3.8 spent 2,048 tokens thinking and answered nothing.
MAX_REPLY_TOKENS = 8192
# Tries a call gets when the provider stalls or fails for a moment, and the pause between them.
TRIES = 3
BACKOFF_SECONDS = 2.0
# The longest pause a rate limit's Retry-After is followed for; a longer one is cut to this.
MAX_RETRY_AFTER_SECONDS = 60.0


class JobRunFailedError(RuntimeError):
    """The run cannot be worked out; the message is the reason the user reads."""


class SelectedModel:
    """The runner's model: the user's selected text model, asked as Studio asks it."""

    def __init__(self, model: ResolvedGeneration, window: int | None) -> None:
        self._model = model
        self.name = model.selection.name
        self.window = window
        local = model.selection.provider == llamacpp.PROVIDER
        self.concurrency = 1 if local else REMOTE_AT_ONCE
        # Anthropic's OpenAI-compatible API refuses a schema without "strict"; from the
        # first refusal on, the prompt alone asks for the JSON, and the runner reads it.
        self._schema_taken = True

    def ask(
        self, system: str, turns: list[tuple[str, str]], schema: dict, shared: int
    ) -> ModelReply:
        messages = [
            Message("system", system),
            *(Message(role, text) for role, text in turns),
        ]
        # Questions over the same passages share a start: one key routes them to one cache.
        shared_start = hashlib.sha256(turns[0][1][:shared].encode()).hexdigest()[:24]
        conversation = f"surfsense-job-{shared_start}"
        if self._schema_taken:
            try:
                return self._reply(messages, schema, conversation)
            except httpx.HTTPStatusError as refused:
                if "response_format" not in str(refused):
                    raise
                logger.info("%s refuses a JSON schema; asking by prompt", self.name)
                self._schema_taken = False
        # Held to no schema, a model follows the one it is shown: without it Sonnet gave
        # quotes as bare strings, which cost it 5 of 15 answers on the live WISP case.
        messages[0] = Message(
            "system",
            f"{system}\n\nYour reply is one JSON object matching this JSON Schema:\n"
            f"{json.dumps(schema)}",
        )
        return self._reply(messages, None, conversation)

    def _reply(
        self, messages: list[Message], schema: dict | None, conversation: str
    ) -> ModelReply:
        """One reply, a transient failure tried again. Still failing, an empty reply, which the
        runner reads as unreadable and leaves to a person: one stream that stalled among a
        workbook's hundreds of calls failed a whole live run."""
        for attempt in range(TRIES):
            try:
                return ModelReply(
                    complete(
                        self._model,
                        messages,
                        max_tokens=MAX_REPLY_TOKENS,
                        json_schema=schema,
                        conversation=conversation,
                    )
                )
            except (StreamTimeoutError, httpx.HTTPError) as failed:
                if not _transient(failed):
                    raise
                logger.warning(
                    "%s: %s, try %d of %d", self.name, failed, attempt + 1, TRIES
                )
                time.sleep(_pause(failed, attempt))
        return ModelReply("")


def _pause(failed: Exception, attempt: int) -> float:
    """How long to wait before trying again: what a rate-limited provider asks for in its
    Retry-After header, within reason, else a pause that grows with each try."""
    if isinstance(failed, httpx.HTTPStatusError):
        asked = _retry_after(failed.response.headers.get("retry-after", ""))
        if asked is not None:
            return min(asked, MAX_RETRY_AFTER_SECONDS)
    return BACKOFF_SECONDS * (attempt + 1)


def _retry_after(value: str) -> float | None:
    """A Retry-After in seconds, from its delay or its HTTP-date form; None when unusable."""
    value = value.strip()
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        seconds = (when - datetime.now(UTC)).total_seconds()
    return max(seconds, 0.0) if math.isfinite(seconds) else None


def _transient(failed: Exception) -> bool:
    """A stall, a dropped connection, a timeout, or the provider's own 408, 429 or 5xx."""
    if isinstance(failed, httpx.HTTPStatusError):
        code = failed.response.status_code
        return code in (408, 429) or code >= 500
    return True


def work_out(
    session: Session, artifact: Artifact, cancelled: Callable[[], bool]
) -> None:
    """Fill in the run's operations and report; a run already worked out is left as it is."""
    meta = artifact.artifact_metadata or {}
    run, revision = job_run_of(meta), revision_of(meta)
    if run is None or revision is None or run.get("report") is not None:
        return
    found = find_job(run["job"])
    if found is None or found[0].manifest.id != run["pack_id"]:
        raise JobRunFailedError(
            f'The job pack for "{run["job"]}" is no longer installed, so the run cannot finish.'
        )
    pack, job = found
    # Checked again here, not only when the run started: Studio's Retry runs a failed or
    # cancelled one afresh, perhaps after its licence has lapsed.
    access = job_access(session, pack.manifest, job)
    if not access.allowed:
        raise JobRunFailedError(access.reason)
    if run["pack_version"] != pack.manifest.version:
        # A retry after an update reads the newer version: the record names what answered.
        run = {**run, "pack_version": pack.manifest.version}
        artifact.artifact_metadata = {**meta, JOB_RUN_KEY: run}
    config = runner_of(job).load_config(pack.path(job.config))
    worked_on = session.get(Document, revision["derived_from_document_id"])
    path = original_path(worked_on) if worked_on is not None else None
    if path is None:
        raise JobRunFailedError("The run's file is no longer on disk.")
    sources = []
    for document_id in run["source_document_ids"]:
        document = session.get(Document, document_id)
        if document is None or not (document.content or "").strip():
            raise JobRunFailedError(f"Source {document_id} is gone or holds no text.")
        sources.append(SourceText(document.id, document.title, document.content))
    model = resolve_routed_generation(session)
    checker = _checker(session, run.get("checker"))
    declared = {s.key for s in config.settings}
    settings = {k: v for k, v in (run.get("settings") or {}).items() if k in declared}
    _, window = asyncio.run(selected_model_window(session))
    embed = _embedder(session)
    engine, artifact_id = session.get_bind(), artifact.id
    progress = RunProgress(
        lambda done, total: write_progress(engine, artifact_id, done, total)
    )
    # Minutes of model calls follow; no transaction may hold the write lock across them.
    session.commit()
    logger.info(
        "job run %s: %s on %s, checked on %s, %d sources, window %s",
        artifact.id,
        job.key,
        model.selection.name,
        checker.selection.name if checker else "the same model",
        len(sources),
        window,
    )
    names = (model.selection.name, checker.selection.name if checker else None)
    options: dict[str, Any] = {
        "on_row": progress.on_row,
        "stop": cancelled,
        "embed": embed,
        "checker": SelectedModel(checker, None) if checker else None,
        "settings": settings,
        "take_turns": _one_at_a_time(model, checker),
    }
    answering = SelectedModel(model, window)
    try:
        if job.runner == CLAUSES_RUNNER:
            review = review_contract(path, sources, config, answering, **options)
            operations, report = review.operations, review_report(review, *names)
        else:
            filled = fill_workbook(path, sources, config, answering, **options)
            operations, report = filled.operations, report_of(filled, config, *names)
    except (NoQuestionsError, NoClausesError) as none:
        raise JobRunFailedError(str(none)) from none
    except PackageRefusedError as refused:
        raise JobRunFailedError(refused.message) from refused
    session.refresh(artifact)
    meta = dict(artifact.artifact_metadata or {})
    meta[REVISION_KEY] = {**revision, "operations": operations}
    meta[JOB_RUN_KEY] = {**run, PROGRESS_KEY: progress.last, "report": report}
    artifact.artifact_metadata = meta
    session.commit()


def _checker(
    session: Session, named: dict[str, Any] | None
) -> ResolvedGeneration | None:
    """The model the firm chose to make the second checks, reached through the API's model route
    as the selected one is; None checks on the answering model. One whose connection is gone
    fails the run before any call, as a retry would otherwise fail its rows one by one."""
    if not named:
        return None
    ref = ModelRef.model_validate(named)
    try:
        check_checker(session, ref)
    except JobSettingsRefusedError as gone:
        raise JobRunFailedError(CHECKER_GONE) from gone
    try:
        url = api_url()
    except ApiNotRunningError as error:
        raise ModelResolutionError(str(error)) from error
    choice = ModelChoice(
        model_type=ModelType.TEXT_GEN,
        provider=ref.provider,
        name=ref.name,
        connection_id=ref.connection_id,
    )
    return ResolvedGeneration(choice, RoutedGenerator(url, ref))


def _one_at_a_time(
    model: ResolvedGeneration, checker: ResolvedGeneration | None
) -> bool:
    """Two different models on the local runtime, which holds one at a time: they take turns."""
    return (
        checker is not None
        and model.selection.provider == llamacpp.PROVIDER
        and checker.selection.provider == llamacpp.PROVIDER
        and model.selection.name != checker.selection.name
    )


def _embedder(session: Session) -> Embed | None:
    """The embedder search uses, so a job finds passages by meaning as chat does; none before
    onboarding chooses one or while its files are missing, and the job then finds them by
    their words alone."""
    index = active_index(session)
    if index is None or encoder.missing_files(index.spec):
        return None
    spec = index.spec

    def embed(texts: list[str], query: bool) -> list[list[float]]:
        purpose = encoder.Purpose.QUERY if query else encoder.Purpose.DOCUMENT
        return encoder.embed(spec, texts, purpose)

    return remembered(embed, f"{spec.id}@{spec.weights.sha256}")


def report_of(
    filled: FillResult, config: JobConfig, model: str, checker: str | None = None
) -> dict[str, Any]:
    """What Studio and the agent say about a run: its counts, each answer's source, its
    exceptions, and for each suggested answer what confirming it writes and where."""
    added = [op["sheet"] for op in filled.operations if op["op"] == "add_sheet"]
    lines = sheet_lines(filled.results)
    # What one step would confirm: none where the cell's dropdown cannot hold the suggestion.
    confirms = [confirmation(r, config) for r in filled.results]
    return {
        "model": model,
        "checker": checker,
        "settings": filled.settings,
        "seconds": filled.seconds,
        "whole_sources": filled.whole_sources,
        "counts": filled.counts,
        "questions": len(filled.results),
        # The suggestions one step confirms: the others are in their comments only.
        "suggested": sum(1 for confirm in confirms if confirm is not None),
        "sheets": {"answers": added[0], "exceptions": added[1]},
        "tables": [
            {"sheet": t.sheet, "header_row": t.header_row, "found_by": t.found_by}
            for t in filled.layout.tables
        ],
        "answers": [
            {
                "sheet": r.row.sheet,
                "cell": r.row.answer_cell,
                "comment_cell": r.row.comment_cell,
                "evidence_cell": r.row.evidence_cell,
                "question": r.row.question,
                "answer": r.answer,
                "said": r.said,
                "written": r.written,
                "suggested": r.suggested,
                # What one step confirms: None when the row has no suggestion its cell can hold.
                "confirm": confirm,
                "lines": line,
                "source": r.source,
                "section": r.section,
                "quote": r.quote,
                "quotes": [
                    {
                        "source": c.source,
                        "section": c.section,
                        "line": c.line,
                        "quote": c.quote,
                    }
                    for c in r.cited
                ],
                "codes": r.codes,
            }
            for r, line, confirm in zip(filled.results, lines, confirms, strict=True)
        ],
        "exceptions": filled.exceptions,
    }
