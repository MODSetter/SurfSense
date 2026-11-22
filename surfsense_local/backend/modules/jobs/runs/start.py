"""Start an installed job on its file and the sources it reads: v1 of a revised copy whose
operations the Studio worker works out, so the user's file is never written."""

from __future__ import annotations

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.service import create_revised_copy
from modules.artifacts.revised_copies.source_file import sha256_of, source_file
from modules.chat.models import ChatThread
from modules.documents.models import Document, DocumentStatus
from modules.jobs.packs.access import job_access
from modules.jobs.packs.installed import find_job
from modules.jobs.packs.manifest import PackRefusedError
from modules.jobs.runners import runner_of
from modules.jobs.runs.record import pending_job_run
from modules.jobs.settings.service import (
    CHECKER_GONE,
    JobSettingsRefusedError,
    check_checker,
    job_settings,
)


class JobRunRefusedError(Exception):
    """A run that cannot start, said in a sentence for the user or the agent."""


def start_job_run(
    session: Session,
    workspace_id: int,
    *,
    job: str,
    document_id: int,
    source_document_ids: list[int],
    chat_thread_id: int | None,
) -> Artifact:
    found = find_job(job)
    if found is None:
        raise JobRunRefusedError(f'No installed job pack has a job named "{job}".')
    pack, pack_job = found
    runner = runner_of(pack_job)
    access = job_access(session, pack.manifest, pack_job)
    if not access.allowed:
        raise JobRunRefusedError(access.reason)
    try:
        config = runner.load_config(pack.path(pack_job.config))
    except PackRefusedError as refused:
        raise JobRunRefusedError(refused.message) from refused
    # The run keeps the firm's choices as they are now: a change applies to the next run.
    chosen = job_settings(session, pack_job.key, config)
    if chosen.checker is not None:
        try:
            check_checker(session, chosen.checker)
        except JobSettingsRefusedError as gone:
            raise JobRunRefusedError(CHECKER_GONE) from gone
    try:
        worked_on = source_file(session, workspace_id, document_id)
    except RevisedCopyRefusedError as refused:
        raise JobRunRefusedError(str(refused)) from refused
    if worked_on.format.format not in runner.formats:
        raise JobRunRefusedError(
            f"{pack_job.name} {runner.takes}; {worked_on.path.name} is not one."
        )
    sources = [i for i in dict.fromkeys(source_document_ids) if i != document_id]
    if not sources:
        raise JobRunRefusedError(f"{pack_job.name} {runner.reads}")
    for document_id in sources:
        document = session.get(Document, document_id)
        if document is None or document.workspace_id != workspace_id:
            raise JobRunRefusedError(
                f"There is no source {document_id} in this workspace."
            )
        if (
            document.status is not DocumentStatus.READY
            or not (document.content or "").strip()
        ):
            raise JobRunRefusedError(
                f'"{document.title}" is not read yet; start the job once it is ready.'
            )
    if chat_thread_id is not None:
        thread = session.get(ChatThread, chat_thread_id)
        if thread is None or thread.workspace_id != workspace_id:
            raise JobRunRefusedError(
                f"There is no chat {chat_thread_id} in this workspace."
            )
    try:
        return create_revised_copy(
            session,
            workspace_id,
            worked_on,
            source_sha256=sha256_of(worked_on.path),
            operations=[],
            chat_thread_id=chat_thread_id,
            job_run=pending_job_run(
                pack_id=pack.manifest.id,
                pack_version=pack.manifest.version,
                job=pack_job.key,
                source_document_ids=sources,
                settings=chosen.values,
                checker=chosen.checker.model_dump() if chosen.checker else None,
            ),
        )
    except RevisedCopyRefusedError as refused:
        raise JobRunRefusedError(str(refused)) from refused
