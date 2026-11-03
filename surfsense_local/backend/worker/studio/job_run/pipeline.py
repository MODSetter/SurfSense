"""A job run's answers, worked out before its revised copy is made: the pack's runner over the
workbook and the run's sources, on the model the user selected.

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
from modules.artifacts.revised_copies.revision import REVISION_KEY, revision_of
from modules.documents.models import Document
from modules.documents.original_file import original_path
from modules.embedding import encoder
from modules.embedding.active import active_index
from modules.jobs.evidence.passages import SourceText
from modules.jobs.evidence.retrieval import Embed
from modules.jobs.evidence.vectors import remembered
from modules.jobs.packs.installed import find_job
from modules.jobs.runs.record import JOB_RUN_KEY, job_run_of
from modules.jobs.workbook_rows.ask import ModelReply
from modules.jobs.workbook_rows.config import load_config
from modules.jobs.workbook_rows.fill import FillResult, fill_workbook
from modules.llm.model_route.client import resolve_routed_generation
from modules.llm.providers import llamacpp
from modules.llm.providers.stream_deadline import StreamTimeoutError
from modules.llm.providers.types import Message
from modules.llm.resolution import ResolvedGeneration
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
    config = load_config(pack.path(job.config))
    workbook = session.get(Document, revision["derived_from_document_id"])
    path = original_path(workbook) if workbook is not None else None
    if path is None:
        raise JobRunFailedError("The questionnaire's file is no longer on disk.")
    sources = []
    for document_id in run["source_document_ids"]:
        document = session.get(Document, document_id)
        if document is None or not (document.content or "").strip():
            raise JobRunFailedError(f"Source {document_id} is gone or holds no text.")
        sources.append(SourceText(document.id, document.title, document.content))
    model = resolve_routed_generation(session)
    _, window = asyncio.run(selected_model_window(session))
    embed = _embedder(session)
    # Minutes of model calls follow; no transaction may hold the write lock across them.
    session.commit()
    logger.info(
        "job run %s: %s on %s, %d sources, window %s",
        artifact.id,
        job.key,
        model.selection.name,
        len(sources),
        window,
    )
    filled = fill_workbook(
        path,
        sources,
        config,
        SelectedModel(model, window),
        stop=cancelled,
        embed=embed,
    )
    session.refresh(artifact)
    meta = dict(artifact.artifact_metadata or {})
    meta[REVISION_KEY] = {**revision, "operations": filled.operations}
    meta[JOB_RUN_KEY] = {**run, "report": report_of(filled, model.selection.name)}
    artifact.artifact_metadata = meta
    session.commit()


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


def report_of(filled: FillResult, model: str) -> dict[str, Any]:
    """What Studio and the agent say about a run: its counts, each answer's source, and its exceptions."""
    return {
        "model": model,
        "seconds": filled.seconds,
        "whole_sources": filled.whole_sources,
        "counts": filled.counts,
        "questions": len(filled.results),
        "tables": [
            {"sheet": t.sheet, "header_row": t.header_row, "found_by": t.found_by}
            for t in filled.layout.tables
        ],
        "answers": [
            {
                "sheet": r.row.sheet,
                "cell": r.row.answer_cell,
                "question": r.row.question,
                "answer": r.answer,
                "said": r.said,
                "written": r.written,
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
            for r in filled.results
        ],
        "exceptions": filled.exceptions,
    }
