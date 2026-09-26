"""The API's installs: one runs at a time, in order, and each can be cancelled.

In memory, like the lock it queues on: one uvicorn worker serves the local app.
"""

import asyncio
import logging
import secrets
import time
from collections.abc import AsyncIterator, Callable, Iterable

from modules.llm.catalog.local.install_jobs.job import InstallJob
from modules.llm.model_type import ModelType

logger = logging.getLogger(__name__)

QUEUED = {"type": "queued", "message": "Waiting for the download ahead of it"}
CHECKING = {"type": "starting", "message": "Checking the model"}
CANCELLED = {"type": "cancelled", "message": "Installation cancelled"}
FAILED = {
    "type": "error",
    "message": "The model could not be installed. Retry the download.",
}

# Long enough for a screen that reconnects to learn how a job it watched ended.
KEEP_FINISHED_SECONDS = 60.0


class InstallJobs:
    def __init__(
        self,
        lock: asyncio.Lock,
        *,
        keep_finished_seconds: float = KEEP_FINISHED_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # The catalog's install lock, which delete also takes.
        self._lock = lock
        self._keep = keep_finished_seconds
        self._clock = clock
        self._jobs: dict[str, InstallJob] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._subscribers: set[asyncio.Event] = set()

    def start(
        self,
        *,
        catalog_id: str,
        label: str,
        model_types: Iterable[ModelType],
        select: bool,
        model_type: ModelType | None,
        steps: Callable[[], AsyncIterator[dict]],
    ) -> InstallJob:
        waiting = self._lock.locked() or bool(self._tasks)
        job = InstallJob(
            id=secrets.token_urlsafe(9),
            catalog_id=catalog_id,
            label=label,
            model_types=tuple(model_types),
            select=select,
            model_type=model_type,
            event=QUEUED if waiting else CHECKING,
        )
        self._jobs[job.id] = job
        self._tasks[job.id] = asyncio.create_task(self._run(job, steps))
        self._changed()
        return job

    def get(self, job_id: str) -> InstallJob | None:
        self._forget_old()
        return self._jobs.get(job_id)

    def list(self) -> list[InstallJob]:
        """Running and waiting jobs, then those finished inside the keep window."""
        self._forget_old()
        return list(self._jobs.values())

    def running(self) -> bool:
        return bool(self._tasks)

    def cancel(self, job_id: str) -> bool:
        """False for a job that is unknown or already over."""
        task = self._tasks.get(job_id)
        if task is None:
            return False
        task.cancel()
        return True

    def subscribe(self) -> asyncio.Event:
        """Set on every change; the subscriber clears it and reads `list()`."""
        changed = asyncio.Event()
        self._subscribers.add(changed)
        return changed

    def unsubscribe(self, changed: asyncio.Event) -> None:
        self._subscribers.discard(changed)

    async def _run(
        self, job: InstallJob, steps: Callable[[], AsyncIterator[dict]]
    ) -> None:
        try:
            if self._lock.locked():
                self._update(job, QUEUED)
            async with self._lock:
                self._update(job, CHECKING)
                async for event in steps():
                    self._update(job, event)
            if not job.finished:
                raise RuntimeError("the install ended without saying how")
        except asyncio.CancelledError:
            # The job, not the task, carries the outcome; a partial file stays
            # as `.part` for the next attempt to resume.
            self._update(job, CANCELLED)
        except Exception:
            logger.exception("model install failed")
            self._update(job, FAILED)
        finally:
            self._tasks.pop(job.id, None)
            self._changed()

    def _update(self, job: InstallJob, event: dict) -> None:
        job.event = event
        if job.finished and job.finished_at is None:
            job.finished_at = self._clock()
        self._changed()

    def _changed(self) -> None:
        for changed in self._subscribers:
            changed.set()

    def _forget_old(self) -> None:
        cutoff = self._clock() - self._keep
        for job_id, job in list(self._jobs.items()):
            if job.finished_at is not None and job.finished_at < cutoff:
                del self._jobs[job_id]
