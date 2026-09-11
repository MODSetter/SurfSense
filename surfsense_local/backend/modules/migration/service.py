import logging
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from modules.chat.models import ChatMessage, ChatThread, MessageRole
from modules.documents.models import Document, DocumentType
from modules.documents.storage import stream_upload, validate_upload
from modules.documents.tasks import ingest_document
from modules.migration.schemas import (
    ExportedThread,
    ExportedThreads,
    Manifest,
    ManifestDocument,
)
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)


def find_or_create_workspaces(
    session: Session, manifest: Manifest
) -> list[tuple[Workspace, bool]]:
    """One local workspace per exported one, keyed by cloud id across re-imports."""
    found: list[tuple[Workspace, bool]] = []
    for exported in manifest.workspaces:
        workspace = session.scalar(
            select(Workspace).where(Workspace.cloud_id == exported.id)
        )
        if workspace is None:
            workspace = Workspace(name=exported.name, cloud_id=exported.id)
            session.add(workspace)
            session.flush()
            found.append((workspace, True))
        else:
            found.append((workspace, False))
    return found


def import_bundle(
    session_factory: sessionmaker[Session],
    bundle_path: Path,
    manifest: Manifest,
    workspace_ids: dict[int, tuple[int, bool]],
) -> None:
    """The slow half, after the 202: documents to disk and queue, threads to rows."""
    try:
        with ZipFile(bundle_path) as archive, session_factory() as session:
            for exported in manifest.workspaces:
                workspace_id, created = workspace_ids[exported.id]
                for document in exported.documents:
                    _import_document(
                        session, archive, workspace_id, exported.id, document
                    )
                # ponytail: threads have no dedup key, so they travel only with
                # a workspace's first import. A later export's new threads are
                # lost; the upgrade is a cloud thread id column on chat_threads.
                if not created:
                    continue
                for thread in ExportedThreads.validate_json(
                    archive.read(exported.chats)
                ):
                    _import_thread(session, workspace_id, thread)
                session.commit()
    finally:
        bundle_path.unlink(missing_ok=True)


def _import_document(
    session: Session,
    archive: ZipFile,
    workspace_id: int,
    cloud_workspace_id: int,
    exported: ManifestDocument,
) -> None:
    storage = get_storage_settings()
    path = PurePosixPath(exported.path)
    with archive.open(exported.path) as member:
        streamed = stream_upload(
            UploadFile(member, filename=path.name),  # type: ignore[arg-type]
            storage.workspace_dir(workspace_id),
        )
    try:
        try:
            mime_type = validate_upload(streamed.path, path.suffix)
        except ValueError as failure:
            logger.warning("skipped %s: %s", exported.path, failure)
            streamed.path.unlink()
            return
        twin = session.scalar(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.dedup_key == streamed.digest,
            )
        )
        if twin is not None:
            streamed.path.unlink()
            return

        # workspaces/<id>/documents/<folder path>/<file>: the hierarchy is kept
        # as data, since the local schema has no folder table.
        folder_path = "/".join(path.parts[3:-1])
        document = Document(
            workspace_id=workspace_id,
            title=exported.title,
            document_type=DocumentType.FILE,
            dedup_key=streamed.digest,
            document_metadata={
                "mime_type": mime_type,
                "size_bytes": streamed.size,
                "suffix": path.suffix,
                "folder_path": folder_path,
                "source": exported.source,
                "cloud": {
                    "workspace_id": cloud_workspace_id,
                    "document_id": exported.id,
                },
            },
        )
        session.add(document)
        session.flush()
    except BaseException:
        streamed.path.unlink(missing_ok=True)
        raise

    destination = storage.document_dir(workspace_id, document.id)
    destination.mkdir(parents=True, exist_ok=True)
    streamed.path.replace(destination / f"original{path.suffix}")
    session.commit()
    ingest_document(document.id)


def _import_thread(
    session: Session, workspace_id: int, exported: ExportedThread
) -> None:
    thread = ChatThread(
        workspace_id=workspace_id, title=exported.title, created_at=exported.created_at
    )
    session.add(thread)
    session.flush()
    for message in exported.messages:
        text = message.text
        if message.citations:
            text += "\n\nSources: " + ", ".join(c.title for c in message.citations)
        session.add(
            ChatMessage(
                chat_thread_id=thread.id,
                role=MessageRole(message.role),
                content={"text": text, "citations": []},
                created_at=message.created_at,
                completed_at=message.created_at,
            )
        )
