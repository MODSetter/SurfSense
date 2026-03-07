import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PipelineLogContext:
    connector_id: int | None
    search_space_id: int
    unique_id: str  # always available from ConnectorDocument
    doc_id: int | None = None  # set once the DB row exists (index phase only)


class LogMessages:
    # prepare_for_indexing
    DOCUMENT_QUEUED = "New document queued for indexing."
    DOCUMENT_UPDATED = "Document content changed, re-queued for indexing."
    DOCUMENT_REQUEUED = "Stuck document re-queued for indexing."
    DOC_SKIPPED_UNKNOWN = "Unexpected error — document skipped."
    BATCH_ABORTED = "Fatal DB error — aborting prepare batch."
    RACE_CONDITION = "Concurrent worker beat us to the commit — rolling back batch."

    # index
    INDEX_STARTED = "Document indexing started."
    INDEX_SUCCESS = "Document indexed successfully."
    LLM_RETRYABLE = (
        "Retryable LLM error — document marked failed, will retry on next sync."
    )
    LLM_PERMANENT = "Permanent LLM error — document marked failed."
    EMBEDDING_FAILED = "Embedding error — document marked failed."
    CHUNKING_OVERFLOW = "Chunking overflow — document marked failed."
    UNEXPECTED = "Unexpected error — document marked failed."


def _format_context(ctx: PipelineLogContext) -> str:
    parts = [
        f"connector_id={ctx.connector_id}",
        f"search_space_id={ctx.search_space_id}",
        f"unique_id={ctx.unique_id}",
    ]
    if ctx.doc_id is not None:
        parts.append(f"doc_id={ctx.doc_id}")
    return " ".join(parts)


def _build_message(msg: str, ctx: PipelineLogContext, **extra) -> str:
    try:
        parts = [msg, _format_context(ctx)]
        for key, val in extra.items():
            parts.append(f"{key}={val}")
        return " ".join(parts)
    except Exception:
        return msg


def _safe_log(
    level_fn, msg: str, ctx: PipelineLogContext, exc_info=None, **extra
) -> None:
    # Logging must never raise — a broken log call inside an except block would
    # chain with the original exception and mask it entirely.
    try:
        message = _build_message(msg, ctx, **extra)
        level_fn(message, exc_info=exc_info)
    except Exception:
        pass


# ── prepare_for_indexing ──────────────────────────────────────────────────────


def log_document_queued(ctx: PipelineLogContext) -> None:
    _safe_log(logger.info, LogMessages.DOCUMENT_QUEUED, ctx)


def log_document_updated(ctx: PipelineLogContext) -> None:
    _safe_log(logger.info, LogMessages.DOCUMENT_UPDATED, ctx)


def log_document_requeued(ctx: PipelineLogContext) -> None:
    _safe_log(logger.info, LogMessages.DOCUMENT_REQUEUED, ctx)


def log_doc_skipped_unknown(ctx: PipelineLogContext, exc: Exception) -> None:
    _safe_log(
        logger.warning, LogMessages.DOC_SKIPPED_UNKNOWN, ctx, exc_info=exc, error=exc
    )


def log_race_condition(ctx: PipelineLogContext) -> None:
    _safe_log(logger.warning, LogMessages.RACE_CONDITION, ctx)


def log_batch_aborted(ctx: PipelineLogContext, exc: Exception) -> None:
    _safe_log(logger.error, LogMessages.BATCH_ABORTED, ctx, exc_info=exc, error=exc)


# ── index ─────────────────────────────────────────────────────────────────────


def log_index_started(ctx: PipelineLogContext) -> None:
    _safe_log(logger.info, LogMessages.INDEX_STARTED, ctx)


def log_index_success(ctx: PipelineLogContext, chunk_count: int) -> None:
    _safe_log(logger.info, LogMessages.INDEX_SUCCESS, ctx, chunk_count=chunk_count)


def log_retryable_llm_error(ctx: PipelineLogContext, exc: Exception) -> None:
    _safe_log(logger.warning, LogMessages.LLM_RETRYABLE, ctx, exc_info=exc, error=exc)


def log_permanent_llm_error(ctx: PipelineLogContext, exc: Exception) -> None:
    _safe_log(logger.error, LogMessages.LLM_PERMANENT, ctx, exc_info=exc, error=exc)


def log_embedding_error(ctx: PipelineLogContext, exc: Exception) -> None:
    _safe_log(logger.error, LogMessages.EMBEDDING_FAILED, ctx, exc_info=exc, error=exc)


def log_chunking_overflow(ctx: PipelineLogContext, exc: Exception) -> None:
    _safe_log(logger.error, LogMessages.CHUNKING_OVERFLOW, ctx, exc_info=exc, error=exc)


def log_unexpected_error(ctx: PipelineLogContext, exc: Exception) -> None:
    _safe_log(logger.error, LogMessages.UNEXPECTED, ctx, exc_info=exc, error=exc)
