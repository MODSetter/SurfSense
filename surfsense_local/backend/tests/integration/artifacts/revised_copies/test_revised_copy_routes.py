"""The routes the Studio panel uses for a revised copy: read it, decide all its changes, download it."""

from urllib.parse import unquote

import pytest
from httpx import AsyncClient, Headers
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.service import create_revised_copy
from modules.artifacts.revised_copies.source_file import sha256_of, source_file
from modules.documents.models import DocumentStatus
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from tests.integration.artifacts.revised_copies.source_files import (
    add_source,
    contract_docx,
    pricing_xlsx,
    word_xml,
)
from tests.integration.worker.conftest import stub_model  # noqa: F401
from worker.studio import run

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

REPLACE = {"op": "replace_text", "quote": "within 30 days", "text": "within 45 days"}
SET_CELL = {"op": "set_cell", "sheet": "Pricing", "cell": "B2", "value": 15000}


def _copy(
    session: Session, workspace: Workspace, name: str, data: bytes, op: dict
) -> int:
    """A ready revised copy's id, the session's transaction ended: each holds the write lock."""
    source = source_file(
        session, workspace.id, add_source(session, workspace.id, name, data)
    )
    artifact = create_revised_copy(
        session,
        workspace.id,
        source,
        source_sha256=sha256_of(source.path),
        operations=[op],
        chat_thread_id=None,
    )
    run(artifact.id)
    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    made = artifact.id
    session.commit()
    return made


def _word(session: Session, workspace: Workspace) -> int:
    return _copy(session, workspace, "MSA_Acme.docx", contract_docx(), REPLACE)


def _filename(headers: Headers) -> str:
    """The saved name, as the browser decodes Content-Disposition."""
    return unquote(headers["content-disposition"].split("filename*=utf-8''")[1])


async def test_reading_a_revised_copy_says_what_it_came_from_and_holds(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """The panel names the user's file and counts what the copy holds."""
    artifact_id = _word(session, workspace)

    reply = await client.get(f"/artifacts/{artifact_id}")

    revision = reply.json()["revision"]
    assert revision["source_name"] == "MSA_Acme.docx"
    assert revision["derived_from_document_id"] is not None
    assert revision["counts"]["comments"] == 0
    assert revision["counts"]["changes"] >= 2
    assert revision["applied"] == 1


async def test_another_artifact_reads_with_no_revision(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """Every other artifact reads as before."""
    artifact_id = _word(session, workspace)
    artifact = session.get(Artifact, artifact_id)
    artifact.artifact_metadata = {
        k: v for k, v in artifact.artifact_metadata.items() if k != "revision"
    }
    session.commit()

    reply = await client.get(f"/artifacts/{artifact_id}")

    assert reply.json()["revision"] is None


async def test_with_changes_downloads_the_marked_up_file_under_the_source_s_name(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """The user recognises the file by its own name."""
    artifact_id = _word(session, workspace)

    reply = await client.get(f"/artifacts/{artifact_id}/revised-copy/download")

    assert reply.status_code == 200
    assert _filename(reply.headers) == "MSA_Acme (revised v1).docx"
    assert "<w:ins " in word_xml(reply.content)


async def test_with_changes_never_falls_back_to_the_file_holding_internal_comments(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """Without its external file, a copy with internal comments has nothing safe to send."""
    artifact_id = _copy(
        session,
        workspace,
        "MSA_Acme.docx",
        contract_docx(),
        {
            "op": "add_comment",
            "quote": "60 days notice",
            "text": "Push back here.",
            "internal": True,
        },
    )
    record = session.get(Artifact, artifact_id).artifact_metadata["revision"]
    (get_storage_settings().data_dir / record["external"]["storage_key"]).unlink()
    session.commit()

    reply = await client.get(f"/artifacts/{artifact_id}/revised-copy/download")

    assert reply.status_code == 404
    assert b"Push back here." not in reply.content


async def test_clean_downloads_every_change_accepted_with_the_translated_suffix(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """The interface passes the suffix in the user's language; the API translates nothing."""
    artifact_id = _word(session, workspace)

    reply = await client.get(
        f"/artifacts/{artifact_id}/revised-copy/download",
        params={"variant": "clean", "suffix": "sauber"},
    )

    assert reply.status_code == 200
    assert _filename(reply.headers) == "MSA_Acme (sauber v1).docx"
    assert "<w:ins " not in word_xml(reply.content)


async def test_a_workbook_has_no_clean_download(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """Only Word has tracked changes to accept into a clean file."""
    artifact_id = _copy(session, workspace, "Pricing.xlsx", pricing_xlsx(), SET_CELL)

    clean = await client.get(
        f"/artifacts/{artifact_id}/revised-copy/download", params={"variant": "clean"}
    )
    changes = await client.get(f"/artifacts/{artifact_id}/revised-copy/download")

    assert clean.status_code == 404
    assert changes.status_code == 200
    assert _filename(changes.headers) == "Pricing (revised v1).xlsx"


async def test_accept_all_makes_the_next_version_from_the_newest(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """The decision is a version, started at once and made by the job."""
    artifact_id = _word(session, workspace)

    reply = await client.post(f"/artifacts/{artifact_id}/revisions/accept-all")

    assert reply.status_code == 202, reply.text
    made = reply.json()
    assert made["version"] == {
        "root_id": artifact_id,
        "number": 2,
        "parent_id": artifact_id,
    }
    assert made["status"] == "pending"


async def test_a_second_decision_while_one_is_being_made_is_a_conflict(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """One version of a copy is made at a time."""
    artifact_id = _word(session, workspace)
    await client.post(f"/artifacts/{artifact_id}/revisions/accept-all")

    reply = await client.post(f"/artifacts/{artifact_id}/revisions/reject-all")

    assert reply.status_code == 409
    assert "still being made" in reply.json()["detail"]


async def test_deciding_all_of_a_workbook_is_a_conflict(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """A workbook has no tracked changes to decide."""
    artifact_id = _copy(session, workspace, "Pricing.xlsx", pricing_xlsx(), SET_CELL)

    reply = await client.post(f"/artifacts/{artifact_id}/revisions/accept-all")

    assert reply.status_code == 409


async def test_retrying_a_failed_version_makes_the_same_edits_again(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """No model is asked: Retry of a revised copy runs its stored edits, not a Studio draft."""
    artifact_id = _word(session, workspace)
    artifact = session.get(Artifact, artifact_id)
    artifact.document.status = DocumentStatus.FAILED
    primary = artifact.files[0].storage_key
    session.commit()

    reply = await client.post(f"/artifacts/{artifact_id}/regenerate")

    assert reply.status_code == 202, reply.text
    run(artifact_id)
    session.expire_all()
    assert session.get(Artifact, artifact_id).document.status is DocumentStatus.READY
    assert (get_storage_settings().data_dir / primary).is_file()
