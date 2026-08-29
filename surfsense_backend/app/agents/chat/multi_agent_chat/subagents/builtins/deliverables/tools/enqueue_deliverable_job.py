"""Interactive tool for durably enqueueing video deliverables."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.capabilities.core import ActivityDescriptor
from app.db import shielded_async_session
from app.deliverables.jobs.dispatch import (
    DeliverableJobDispatcher,
    dispatch_deliverable_job,
)
from app.deliverables.jobs.policy import VIDEO_KIND
from app.deliverables.jobs.service import create_deliverable_job

from .thread_resolver import resolve_root_thread_id

logger = logging.getLogger(__name__)

_MAX_TITLE_CHARS = 500
_MAX_BRIEF_CHARS = 16_000
_MAX_SOURCE_REFERENCES = 25
_MAX_SOURCE_REFERENCE_CHARS = 1_000


def _normalized_request(
    *,
    brief: str,
    source_references: Sequence[str] | None,
    revision_artifact_id: int | None,
    root_thread_id: int,
) -> dict[str, Any]:
    normalized_brief = " ".join(brief.split())
    if not normalized_brief:
        raise ValueError("brief must not be empty")
    if len(normalized_brief) > _MAX_BRIEF_CHARS:
        raise ValueError("brief is too long")
    if revision_artifact_id is not None and (
        isinstance(revision_artifact_id, bool) or revision_artifact_id <= 0
    ):
        raise ValueError("revision_artifact_id must be a positive integer")

    sources: list[str] = []
    seen: set[str] = set()
    for raw_reference in source_references or ():
        reference = " ".join(raw_reference.split())
        if not reference or reference in seen:
            continue
        if len(reference) > _MAX_SOURCE_REFERENCE_CHARS:
            raise ValueError("source reference is too long")
        seen.add(reference)
        sources.append(reference)
    if len(sources) > _MAX_SOURCE_REFERENCES:
        raise ValueError("too many source references")

    return {
        "version": 1,
        "brief": normalized_brief,
        "source_references": sources,
        "revision_artifact_id": revision_artifact_id,
        "root_thread_id": root_thread_id,
    }


def create_enqueue_deliverable_job_tool(
    *,
    workspace_id: int,
    created_by_id: str | UUID | None = None,
    dispatcher: DeliverableJobDispatcher = dispatch_deliverable_job,
) -> BaseTool:
    """Build the interactive-only video enqueue tool."""

    @tool
    async def enqueue_deliverable_job(
        title: str,
        brief: str,
        runtime: ToolRuntime,
        source_references: list[str] | None = None,
        revision_artifact_id: int | None = None,
    ) -> Command:
        """Validate and queue a video deliverable, then return immediately.

        Use only for requested video, animation, or narrated audiovisual output.
        `brief` contains the normalized creative request. `source_references`
        contains only relevant workspace handles or source labels. For an
        in-place revision, set `revision_artifact_id` to the existing artifact.
        The pending card owns all later authoring, narration, rendering,
        verification, and saving.
        """
        normalized_title = " ".join(title.split())
        if not normalized_title or len(normalized_title) > _MAX_TITLE_CHARS:
            raise ValueError("title must be between 1 and 500 characters")
        root_thread_id = resolve_root_thread_id(runtime)
        request = _normalized_request(
            brief=brief,
            source_references=source_references,
            revision_artifact_id=revision_artifact_id,
            root_thread_id=root_thread_id,
        )
        creator = UUID(str(created_by_id)) if created_by_id else None

        try:
            async with shielded_async_session() as session:
                job, created = await create_deliverable_job(
                    session,
                    kind=VIDEO_KIND,
                    title=normalized_title,
                    workspace_id=workspace_id,
                    thread_id=root_thread_id,
                    created_by_id=creator,
                    tool_call_id=runtime.tool_call_id,
                    request=request,
                )
                job_id = job.id
                task_id = job.celery_task_id
                if not task_id:
                    raise RuntimeError("queued deliverable has no dispatch identity")
                await session.commit()

            if created:
                try:
                    dispatcher(
                        job_id=job_id,
                        task_id=task_id,
                    )
                except Exception:
                    # The committed queued row is the outbox. Reconciliation can
                    # publish it later; broker/provider details are never public.
                    logger.exception(
                        "Could not publish queued deliverable job %s", job_id
                    )
        except Exception:
            logger.exception("Could not create queued video deliverable")
            error = "Video generation could not start. Please try again."
            return with_receipt(
                payload={"status": "failed", "error": error},
                receipt=make_receipt(
                    route="deliverables",
                    type="deliverable_job",
                    operation="generate",
                    status="failed",
                    error=error,
                ),
                tool_call_id=runtime.tool_call_id,
            )

        return with_receipt(
            payload={
                "status": "pending",
                "job_id": job_id,
                "title": normalized_title,
                "message": "Your video is being generated. You can continue chatting.",
            },
            receipt=make_receipt(
                route="deliverables",
                type="deliverable_job",
                operation="generate",
                status="pending",
                external_id=str(job_id),
                preview=normalized_title,
            ),
            tool_call_id=runtime.tool_call_id,
        )

    enqueue_deliverable_job.metadata = {
        "activity_descriptor": ActivityDescriptor(
            active_title="Starting video generation",
            completed_title="Video generation in progress",
            category="artifact",
            icon_key="clapperboard",
            kind="enqueue_deliverable_job",
        ).as_metadata()
    }
    return enqueue_deliverable_job
