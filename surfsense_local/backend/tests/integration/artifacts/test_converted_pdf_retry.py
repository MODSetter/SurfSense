"""Retrying a converted PDF in Studio: the same file is converted again, with no model and no sources."""

from io import BytesIO

import docx
import pytest
from sqlalchemy.orm import Session

from modules.artifacts.converted_documents.conversion import Conversion
from modules.artifacts.converted_documents.service import create_conversion
from modules.artifacts.made_file import keep_made_file
from modules.artifacts.service import regenerate_artifact
from modules.documents.models import DocumentStatus
from modules.workspaces.models import Workspace
from tests.integration.worker.conftest import stub_model  # noqa: F401
from tests.office_stand_in import office_on
from worker.studio import run

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]


def _word(session: Session, workspace: Workspace) -> int:
    """A ready Word artifact, the kind the agent renders and then converts."""
    document = docx.Document()
    document.add_paragraph("Board pack")
    out = BytesIO()
    document.save(out)
    word = keep_made_file(
        session,
        workspace.id,
        title="Board pack",
        format="docx",
        data=out.getvalue(),
        made_by={"tool": "test"},
        document_ids=[],
        artifact_ids=[],
        chat_thread_id=None,
    )
    run(word.id)
    session.expire_all()
    assert word.document.status is DocumentStatus.READY
    return word.id


def test_retrying_a_failed_conversion_of_an_artifact_converts_it_again(
    session: Session, workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PDF converted from an artifact has no sources to re-resolve, and asks no model."""
    word_id = _word(session, workspace)
    office_on(monkeypatch, failure="LibreOffice timed out")
    pdf = create_conversion(session, workspace, Conversion(artifact_id=word_id))
    run(pdf.id)
    session.expire_all()
    assert pdf.document.status is DocumentStatus.FAILED

    office = office_on(monkeypatch, pages=2)
    regenerate_artifact(session, pdf)
    run(pdf.id)

    session.expire_all()
    assert pdf.document.status is DocumentStatus.READY, pdf.document.error_message
    assert pdf.generation == 2
    assert [suffix for suffix, _ in office.read] == [".docx"]
