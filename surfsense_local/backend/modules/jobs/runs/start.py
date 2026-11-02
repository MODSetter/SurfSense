"""Start an installed job on a workbook and the sources to answer from: v1 of a revised copy
whose operations the Studio worker works out, so the user's file is never written."""

from __future__ import annotations

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.refusals import RevisedCopyRefusedError
from modules.artifacts.revised_copies.service import create_revised_copy
from modules.artifacts.revised_copies.source_file import sha256_of, source_file
from modules.documents.models import Document, DocumentStatus
from modules.jobs.packs.access import pack_access
from modules.jobs.packs.installed import find_job
from modules.jobs.runs.record import pending_job_run


class JobRunRefusedError(Exception):
    """A run that cannot start, said in a sentence for the user or the agent."""


def start_job_run(
    session: Session,
    workspace_id: int,
    *,
    job: str,
    workbook_document_id: int,
    source_document_ids: list[int],
    chat_thread_id: int | None,
) -> Artifact:
    found = find_job(job)
    if found is None:
        raise JobRunRefusedError(f'No installed job pack has a job named "{job}".')
    pack, pack_job = found
    access = pack_access(session, pack.manifest)
    if not access.allowed:
        raise JobRunRefusedError(access.reason)
    try:
        workbook = source_file(session, workspace_id, workbook_document_id)
    except RevisedCopyRefusedError as refused:
        raise JobRunRefusedError(str(refused)) from refused
    if workbook.format.format != "xlsx":
        raise JobRunRefusedError(
            f"{pack_job.name} fills in a workbook (.xlsx or .xlsm); "
            f"{workbook.path.name} is not one."
        )
    sources = [
        i for i in dict.fromkeys(source_document_ids) if i != workbook_document_id
    ]
    if not sources:
        raise JobRunRefusedError(
            f"{pack_job.name} answers from the firm's own documents: select them too."
        )
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
    try:
        return create_revised_copy(
            session,
            workspace_id,
            workbook,
            source_sha256=sha256_of(workbook.path),
            operations=[],
            chat_thread_id=chat_thread_id,
            job_run=pending_job_run(
                pack_id=pack.manifest.id,
                pack_version=pack.manifest.version,
                job=pack_job.key,
                source_document_ids=sources,
            ),
        )
    except RevisedCopyRefusedError as refused:
        raise JobRunRefusedError(str(refused)) from refused
