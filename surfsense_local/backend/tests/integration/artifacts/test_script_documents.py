"""Creating a document script's artifact: v1 of a new document, or its next version."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.script_documents.service import (
    ScriptDocumentRefusedError,
    create_script_document,
)
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.queue import studio_queue

pytestmark = pytest.mark.integration

SCRIPT = "import docx\ndocx.Document().save(OUTPUT_PATH)\n"


def _create(session: Session, workspace: Workspace, **overrides: Any) -> Artifact:
    request: dict[str, Any] = {
        "title": "Client proposal",
        "format": "docx",
        "script": SCRIPT,
        "base_artifact_id": None,
        "image_names": [],
    }
    return create_script_document(session, workspace, **{**request, **overrides})


def _studio_artifact(session: Session, workspace: Workspace) -> Artifact:
    """An artifact Studio's own Word button made: no spec, no version."""
    document = Document(
        workspace_id=workspace.id,
        title="Word",
        document_type=DocumentType.ARTIFACT,
        status=DocumentStatus.READY,
    )
    session.add(document)
    session.flush()
    artifact = Artifact(
        document_id=document.id,
        workspace_id=workspace.id,
        format="docx",
        artifact_metadata={"source_document_ids": [], "prompt": None, "options": None},
    )
    session.add(artifact)
    session.commit()
    return artifact


def _artifact_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Artifact)) or 0


def test_a_first_version_is_its_own_root_and_waits_in_the_studio_queue(
    session: Session, workspace: Workspace
) -> None:
    """v1 roots its own lineage; the job is queued after the row is committed."""
    artifact = _create(session, workspace)

    session.expire_all()
    assert artifact.format == "docx"
    assert artifact.document.title == "Client proposal"
    assert artifact.document.document_type is DocumentType.ARTIFACT
    assert artifact.document.status is DocumentStatus.PENDING
    assert artifact.artifact_metadata == {
        "spec": {
            "kind": "python",
            "text": SCRIPT,
            "format": "docx",
            "images": [],
            "template_source_id": None,
        },
        "version": {"root": artifact.id, "number": 1, "parent": None},
        "source_document_ids": [],
        "prompt": None,
    }
    assert [job.args for job in studio_queue.pending()] == [(artifact.id,)]


def test_each_next_version_keeps_the_root_and_names_its_parent(
    session: Session, workspace: Workspace
) -> None:
    """Each version points at the first and at the one it was made from."""
    first = _create(session, workspace)
    second = _create(session, workspace, base_artifact_id=first.id, script="v2")
    third = _create(session, workspace, base_artifact_id=second.id, script="v3")

    assert second.artifact_metadata["version"] == {
        "root": first.id,
        "number": 2,
        "parent": first.id,
    }
    assert third.artifact_metadata["version"] == {
        "root": first.id,
        "number": 3,
        "parent": second.id,
    }
    assert third.artifact_metadata["spec"]["text"] == "v3"


def test_a_version_made_from_an_older_one_takes_the_next_free_number(
    session: Session, workspace: Workspace
) -> None:
    """Two v3s would make the switcher ambiguous; the parent says where it came from."""
    first = _create(session, workspace)
    _create(session, workspace, base_artifact_id=first.id)

    branched = _create(session, workspace, base_artifact_id=first.id)

    assert branched.artifact_metadata["version"] == {
        "root": first.id,
        "number": 3,
        "parent": first.id,
    }


def test_documents_number_their_versions_apart(
    session: Session, workspace: Workspace
) -> None:
    """Numbering is per root: another document's versions do not count."""
    proposal = _create(session, workspace)
    _create(session, workspace, base_artifact_id=proposal.id)
    letter = _create(session, workspace, title="Cover letter")

    next_letter = _create(session, workspace, base_artifact_id=letter.id)

    assert next_letter.artifact_metadata["version"]["number"] == 2


def test_named_images_are_kept_in_the_spec_and_their_sources_recorded_once(
    session: Session, workspace: Workspace, source_figure: str
) -> None:
    """A figure named twice is copied once; its source is recorded as grounding."""
    source_id = int(source_figure.split("-")[0])

    artifact = _create(session, workspace, image_names=[source_figure, source_figure])

    assert artifact.artifact_metadata["spec"]["images"] == [source_figure]
    assert artifact.artifact_metadata["source_document_ids"] == [source_id]


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"title": "  "}, "title"),
        ({"title": "x" * 201}, "title"),
        ({"script": ""}, "script"),
        ({"script": "x" * 200_001}, "script"),
        ({"format": "odt"}, "docx, pdf, pptx or xlsx"),
        ({"image_names": ["999-1"]}, '"999-1"'),
        ({"image_names": ["../../surfsense.db"]}, '"../../surfsense.db"'),
        ({"base_artifact_id": 999}, "999"),
    ],
)
def test_a_request_it_cannot_carry_out_is_refused_with_a_reason_and_writes_nothing(
    session: Session, workspace: Workspace, overrides: dict[str, Any], reason: str
) -> None:
    """Nothing is stored or queued for a request that fails validation."""
    with pytest.raises(ScriptDocumentRefusedError, match=reason):
        _create(session, workspace, **overrides)

    session.rollback()
    assert _artifact_count(session) == 0
    assert studio_queue.pending() == []


def test_a_base_in_another_workspace_is_refused(
    session: Session, workspace: Workspace
) -> None:
    """Another workspace's artifact is as good as missing."""
    elsewhere = Workspace(name="Elsewhere")
    session.add(elsewhere)
    session.commit()
    theirs = _create(session, elsewhere)

    with pytest.raises(ScriptDocumentRefusedError, match=f"no artifact {theirs.id}"):
        _create(session, workspace, base_artifact_id=theirs.id)


def test_an_image_from_another_workspace_is_refused(
    session: Session, source_figure: str
) -> None:
    """Image names resolve only within the workspace the document is made in."""
    elsewhere = Workspace(name="Elsewhere")
    session.add(elsewhere)
    session.commit()

    with pytest.raises(ScriptDocumentRefusedError, match=f'"{source_figure}"'):
        _create(session, elsewhere, image_names=[source_figure])


def test_an_artifact_studio_made_cannot_be_a_base(
    session: Session, workspace: Workspace
) -> None:
    """Studio's drafted artifacts keep no script, so there is nothing to edit."""
    studio = _studio_artifact(session, workspace)

    with pytest.raises(ScriptDocumentRefusedError, match="has no versions"):
        _create(session, workspace, base_artifact_id=studio.id)


def test_a_pdf_cannot_continue_a_word_document(
    session: Session, workspace: Workspace
) -> None:
    """A PDF of the same proposal is a document of its own, with its own v1."""
    word = _create(session, workspace)

    with pytest.raises(ScriptDocumentRefusedError, match="Word document"):
        _create(session, workspace, format="pdf", base_artifact_id=word.id)


async def test_the_artifact_reads_carry_the_version_and_the_spec_kind(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """The list and the detail both say which version an artifact is."""
    first = _create(session, workspace)
    second = _create(session, workspace, base_artifact_id=first.id)

    listed = await client.get(f"/workspaces/{workspace.id}/artifacts")
    detail = await client.get(f"/artifacts/{second.id}")

    by_id = {item["id"]: item for item in listed.json()}
    assert by_id[first.id]["version"] == {
        "root_id": first.id,
        "number": 1,
        "parent_id": None,
    }
    assert by_id[second.id]["version"] == {
        "root_id": first.id,
        "number": 2,
        "parent_id": first.id,
    }
    assert by_id[second.id]["spec_kind"] == "python"
    assert detail.json()["version"] == by_id[second.id]["version"]
    assert detail.json()["spec_kind"] == "python"


async def test_an_ordinary_artifact_reads_as_before(
    client: AsyncClient, session: Session, workspace: Workspace
) -> None:
    """Studio's own artifacts carry no version and no spec, as before this slice."""
    studio = _studio_artifact(session, workspace)

    listed = await client.get(f"/workspaces/{workspace.id}/artifacts")
    detail = await client.get(f"/artifacts/{studio.id}")

    assert listed.json()[0]["version"] is None
    assert listed.json()[0]["spec_kind"] is None
    assert detail.json()["version"] is None
    assert detail.json()["spec_kind"] is None
    assert detail.json()["format"] == "docx"


@pytest.mark.parametrize("format", ["pptx", "xlsx"])
def test_a_deck_or_a_workbook_is_a_document_script_too(
    session: Session, workspace: Workspace, format: str
) -> None:
    """PowerPoint and Excel are kept as scripts with versions, as Word and PDF are."""
    first = _create(session, workspace, format=format)
    second = _create(session, workspace, format=format, base_artifact_id=first.id)

    assert first.format == format
    assert first.artifact_metadata["spec"]["format"] == format
    assert second.artifact_metadata["version"]["root"] == first.id


def _uploaded(session: Session, workspace: Workspace, file_name: str) -> Document:
    """A source the user uploaded, its original kept as ingest keeps it."""
    source = Document(
        workspace_id=workspace.id,
        title=file_name,
        document_type=DocumentType.FILE,
        status=DocumentStatus.READY,
        content="Brand guide",
    )
    session.add(source)
    session.commit()
    folder = get_storage_settings().document_dir(workspace.id, source.id)
    folder.mkdir(parents=True)
    (folder / file_name).write_bytes(b"PK\x03\x04 an office file")
    return source


@pytest.mark.parametrize(
    ("format", "file_name"), [("docx", "Letterhead.docx"), ("pptx", "Brand.pptx")]
)
def test_a_template_source_is_kept_in_the_spec_and_recorded_as_a_source(
    session: Session, workspace: Workspace, format: str, file_name: str
) -> None:
    """The run copies the template from the spec; the source grounds the document."""
    template = _uploaded(session, workspace, file_name)

    artifact = _create(
        session, workspace, format=format, template_source_id=template.id
    )

    assert artifact.artifact_metadata["spec"]["template_source_id"] == template.id
    assert artifact.artifact_metadata["source_document_ids"] == [template.id]


def test_the_next_version_keeps_its_template_unless_the_call_names_another(
    session: Session, workspace: Workspace
) -> None:
    """A call that leaves the template out still starts from it; naming one swaps it."""
    brand = _uploaded(session, workspace, "Brand.pptx")
    rebrand = _uploaded(session, workspace, "Rebrand.pptx")
    first = _create(session, workspace, format="pptx", template_source_id=brand.id)

    second = _create(session, workspace, format="pptx", base_artifact_id=first.id)
    third = _create(
        session,
        workspace,
        format="pptx",
        base_artifact_id=second.id,
        template_source_id=rebrand.id,
    )

    assert second.artifact_metadata["spec"]["template_source_id"] == brand.id
    assert third.artifact_metadata["spec"]["template_source_id"] == rebrand.id


@pytest.mark.parametrize(
    ("format", "file_name", "reason"),
    [
        ("docx", "Brand.pptx", "not a Word file"),
        ("pptx", "Letterhead.docx", "not a PowerPoint file"),
        ("docx", "Plan.pdf", "not a Word file"),
        ("pdf", "Letterhead.docx", "Word document or a PowerPoint deck"),
        ("xlsx", "Budget.xlsx", "Word document or a PowerPoint deck"),
    ],
)
def test_a_template_that_does_not_fit_the_format_is_refused(
    session: Session, workspace: Workspace, format: str, file_name: str, reason: str
) -> None:
    """Only a .docx starts a Word document and only a .pptx a deck; nothing else takes one."""
    template = _uploaded(session, workspace, file_name)

    with pytest.raises(ScriptDocumentRefusedError, match=reason):
        _create(session, workspace, format=format, template_source_id=template.id)

    session.rollback()
    assert _artifact_count(session) == 0


def test_a_template_that_is_no_uploaded_file_in_this_workspace_is_refused(
    session: Session, workspace: Workspace
) -> None:
    """A note has no file to start from, and another workspace's source is as good as missing."""
    note = Document(
        workspace_id=workspace.id,
        title="Plan",
        document_type=DocumentType.NOTE,
        status=DocumentStatus.READY,
        content="We ship on Friday.",
    )
    elsewhere = Workspace(name="Elsewhere")
    session.add_all([note, elsewhere])
    session.commit()
    theirs = _uploaded(session, elsewhere, "Brand.pptx")

    for source_id in (note.id, theirs.id, 999):
        with pytest.raises(
            ScriptDocumentRefusedError, match=f"source file {source_id}"
        ):
            _create(session, workspace, format="pptx", template_source_id=source_id)


def test_a_next_version_whose_template_was_deleted_is_refused_with_what_to_do(
    session: Session, workspace: Workspace
) -> None:
    """The model learns the template is gone and how to go on without it."""
    brand = _uploaded(session, workspace, "Brand.pptx")
    first = _create(session, workspace, format="pptx", template_source_id=brand.id)
    session.delete(brand)
    session.commit()

    with pytest.raises(ScriptDocumentRefusedError) as refused:
        _create(session, workspace, format="pptx", base_artifact_id=first.id)

    assert f"made from template source {brand.id}" in str(refused.value)
    assert "template_source_id" in str(refused.value)
