"""Task dispatcher abstraction for background document processing.

Decouples the upload endpoint from Celery so tests can swap in a
synchronous (inline) implementation that needs only PostgreSQL.
"""

from __future__ import annotations

from typing import Protocol


class TaskDispatcher(Protocol):
    async def dispatch_file_processing(
        self,
        *,
        document_id: int,
        temp_path: str,
        filename: str,
        search_space_id: int,
        user_id: str,
        should_summarize: bool = False,
    ) -> None: ...


class CeleryTaskDispatcher:
    """Production dispatcher — fires Celery tasks via Redis broker."""

    async def dispatch_file_processing(
        self,
        *,
        document_id: int,
        temp_path: str,
        filename: str,
        search_space_id: int,
        user_id: str,
        should_summarize: bool = False,
    ) -> None:
        from app.tasks.celery_tasks.document_tasks import (
            process_file_upload_with_document_task,
        )

        process_file_upload_with_document_task.delay(
            document_id=document_id,
            temp_path=temp_path,
            filename=filename,
            search_space_id=search_space_id,
            user_id=user_id,
            should_summarize=should_summarize,
        )


async def get_task_dispatcher() -> TaskDispatcher:
    return CeleryTaskDispatcher()
