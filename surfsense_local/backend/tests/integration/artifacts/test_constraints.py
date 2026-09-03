"""Artifacts: the sidecar shape ADR-0003 depends on."""

import pytest
from sqlalchemy import Connection, Engine, delete, exc, insert, select

from modules.artifacts.models import Artifact, ArtifactFile, ArtifactFileRole
from modules.chat.models import ChatThread
from modules.documents.models import Document, DocumentType
from modules.workspaces.models import Workspace

pytestmark = pytest.mark.integration


def _artifact_document(connection: Connection, document_id: int) -> None:
    connection.execute(
        insert(Document).values(
            id=document_id,
            workspace_id=1,
            title="deck",
            document_type=DocumentType.ARTIFACT,
        )
    )


def test_a_document_carries_at_most_one_artifact(engine: Engine) -> None:
    """The sidecar is one-to-one; a second row would fork the artifact history."""
    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="one"))
        _artifact_document(connection, 1)
        connection.execute(
            insert(Artifact).values(document_id=1, workspace_id=1, format="pptx")
        )

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(Artifact).values(document_id=1, workspace_id=1, format="pptx")
        )


def test_deleting_a_thread_keeps_the_artifact_it_produced(engine: Engine) -> None:
    """Clearing chat history must not delete the deliverables it generated."""
    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="one"))
        connection.execute(insert(ChatThread).values(id=1, workspace_id=1))
        _artifact_document(connection, 1)
        connection.execute(
            insert(Artifact).values(
                document_id=1, workspace_id=1, chat_thread_id=1, format="pptx"
            )
        )
        connection.execute(delete(ChatThread).where(ChatThread.id == 1))

        surviving = connection.execute(select(Artifact.chat_thread_id)).one()
        assert surviving.chat_thread_id is None


def test_an_artifact_holds_one_file_per_role(engine: Engine) -> None:
    """Roles are slots, not a list: a second preview would make renders ambiguous."""
    file = {
        "role": ArtifactFileRole.PREVIEW,
        "original_filename": "deck.png",
        "mime_type": "image/png",
        "size_bytes": 1024,
        "checksum_sha256": "a" * 64,
    }
    with engine.begin() as connection:
        connection.execute(insert(Workspace).values(id=1, name="one"))
        _artifact_document(connection, 1)
        connection.execute(
            insert(Artifact).values(id=1, document_id=1, workspace_id=1, format="pptx")
        )
        connection.execute(
            insert(ArtifactFile).values(artifact_id=1, storage_key="first", **file)
        )

    with pytest.raises(exc.IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(ArtifactFile).values(artifact_id=1, storage_key="second", **file)
        )
