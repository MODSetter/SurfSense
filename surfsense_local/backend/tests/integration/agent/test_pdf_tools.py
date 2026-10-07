"""The PDF tools as opencode's MCP client calls them: new PDF artifacts, the user's files untouched."""

import re
from io import BytesIO

import pypdf
import pytest
from sqlalchemy import Engine

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.pdf_tools import opened_pdf
from modules.source_scope.schemas import SourceScope
from shared.config import get_storage_settings
from shared.db import create_session_factory
from tests.integration.agent.conftest import declare_image_input
from tests.integration.agent.test_office_documents import _uploaded
from tests.integration.agent.tool_endpoint_client import ToolEndpoint
from tests.integration.worker.conftest import stub_model  # noqa: F401
from tests.unit.pdf_tools.pdfs import form, locked, long_choices, numbered, texts

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

_MADE = re.compile(r"Made artifact (\d+): (.+)")


def _made(text: str) -> int:
    """The artifact a PDF tool's result names on its first line."""
    match = _MADE.fullmatch(text.split("\n", 1)[0])
    assert match is not None, text
    return int(match[1])


def _artifact(engine: Engine, artifact_id: int) -> tuple[Artifact, bytes]:
    with create_session_factory(engine)() as session:
        artifact = session.get(Artifact, artifact_id)
        assert artifact is not None
        (primary,) = [f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY]
        data = (get_storage_settings().data_dir / primary.storage_key).read_bytes()
        session.expunge_all()
        return artifact, data


def _original(workspace_id: int, source_id: int, name: str) -> bytes:
    folder = get_storage_settings().document_dir(workspace_id, source_id)
    return (folder / name).read_bytes()


async def test_merging_two_sources_makes_a_new_pdf_artifact_studio_lists(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """The merge is the user's to find in Studio, and neither source's bytes change."""
    workspace_id = await tools.workspace()
    report, annex = numbered(2, "Report"), numbered(1, "Annex")
    first = _uploaded(engine, workspace_id, "Report.pdf", report)
    second = _uploaded(engine, workspace_id, "Annex.pdf", annex)

    text, is_error = await tools.call(
        workspace_id,
        "pdf_pages",
        {"operation": "merge", "document_ids": [second, first], "title": "Pack"},
    )

    assert is_error is False, text
    artifact_id = _made(text)
    assert text.split("\n", 1)[0] == f"Made artifact {artifact_id}: Pack"
    assert "A new PDF of 3 pages in Studio" in text
    assert "unchanged" in text
    artifact, data = _artifact(engine, artifact_id)
    assert texts(data) == ["Annex 1", "Report 1", "Report 2"]
    assert artifact.format == "pdf"
    assert artifact.artifact_metadata["derived_from"] == {
        "document_ids": [second, first],
        "artifact_ids": [],
    }
    assert artifact.artifact_metadata["made_by"]["operation"] == "merge"
    listed = await tools.client.get(f"/workspaces/{workspace_id}/artifacts")
    assert [(a["id"], a["title"]) for a in listed.json()] == [(artifact_id, "Pack")]
    assert _original(workspace_id, first, "Report.pdf") == report
    assert _original(workspace_id, second, "Annex.pdf") == annex


async def test_a_model_that_reads_images_gets_the_new_pages_inline(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """The model checks the pages it made, as it does a render's; copies stay for a closer look."""
    declare_image_input(True)
    workspace_id = await tools.workspace()
    source = _uploaded(engine, workspace_id, "Deck.pdf", numbered(6))

    text, images, is_error = await tools.call_content(
        workspace_id,
        "pdf_pages",
        {"operation": "extract", "document_ids": [source], "pages": "6,1-2"},
    )

    assert is_error is False, text
    artifact_id = _made(text)
    assert text.split("\n", 1)[0] == f"Made artifact {artifact_id}: Deck (pages 6,1-2)"
    assert "Pages 1, 2 and 3 come with this result as images, in order." in text
    assert len(images) == 3
    previews = tools.folder(workspace_id) / "outputs" / "previews" / str(artifact_id)
    assert sorted(p.name for p in previews.glob("*.png")) == [
        "page-1.png",
        "page-2.png",
        "page-3.png",
    ]
    assert f"outputs/previews/{artifact_id}/" in text


async def test_a_model_that_reads_no_images_is_told_there_are_no_previews(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """opencode would turn each image into an error for this model, so none is sent."""
    workspace_id = await tools.workspace()
    source = _uploaded(engine, workspace_id, "Deck.pdf", numbered(2))

    text, images, is_error = await tools.call_content(
        workspace_id,
        "pdf_pages",
        {"operation": "rotate", "document_ids": [source], "angle": 90},
    )

    assert is_error is False, text
    assert images == []
    assert "No page previews: the selected model cannot read images." in text
    _, data = _artifact(engine, _made(text))
    assert [page.rotation for page in pypdf.PdfReader(BytesIO(data)).pages] == [90, 90]


async def test_a_pdf_artifact_can_be_worked_on_again(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """One tool's result is the next one's input, recorded as what the new PDF came from."""
    workspace_id = await tools.workspace()
    source = _uploaded(engine, workspace_id, "Deck.pdf", numbered(4))
    first, _ = await tools.call(
        workspace_id,
        "pdf_pages",
        {"operation": "reorder", "document_ids": [source], "pages": "4-1"},
    )
    reordered = _made(first)

    text, is_error = await tools.call(
        workspace_id,
        "pdf_stamp",
        {"artifact_id": reordered, "kind": "page_numbers", "text": "{page} of {total}"},
    )

    assert is_error is False, text
    artifact, data = _artifact(engine, _made(text))
    assert ["4 of 4" in page for page in texts(data)] == [False, False, False, True]
    assert texts(data)[0].startswith("Page 4")
    assert artifact.artifact_metadata["derived_from"] == {
        "document_ids": [],
        "artifact_ids": [reordered],
    }


async def test_split_makes_one_artifact_per_range(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """Each part is its own artifact, named by the pages it holds."""
    workspace_id = await tools.workspace()
    source = _uploaded(engine, workspace_id, "Minutes.pdf", numbered(5))

    text, is_error = await tools.call(
        workspace_id,
        "pdf_pages",
        {"operation": "split", "document_ids": [source], "pages": "1-2,3-"},
    )

    assert is_error is False, text
    made = [int(n) for n in re.findall(r"^- artifact (\d+): ", text, re.M)]
    assert len(made) == 2
    assert "Minutes (pages 1-2), 2 pages" in text
    assert "Minutes (pages 3-5), 3 pages" in text
    assert [texts(_artifact(engine, n)[1]) for n in made] == [
        ["Page 1", "Page 2"],
        ["Page 3", "Page 4", "Page 5"],
    ]


async def test_an_unticked_source_is_refused(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """A PDF tool holds to the turn's ticked sources, as every tool does, and makes nothing."""
    workspace_id = await tools.workspace()
    ticked = _uploaded(engine, workspace_id, "A.pdf", numbered(1))
    unticked = _uploaded(engine, workspace_id, "B.pdf", numbered(1))
    thread = tools.thread(workspace_id, SourceScope(document_ids=[ticked]))

    text, is_error = await tools.call(
        workspace_id,
        "pdf_pages",
        {"operation": "merge", "document_ids": [ticked, unticked]},
        thread=thread,
    )

    assert is_error is True
    assert f"Source {unticked} is not selected for this request." in text
    with create_session_factory(engine)() as session:
        assert session.query(Artifact).count() == 0


async def test_an_artifact_from_another_workspace_is_refused(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """An artifact id is only good inside its own workspace."""
    mine = await tools.workspace()
    theirs = await tools.workspace()
    source = _uploaded(engine, theirs, "Theirs.pdf", numbered(1))
    made, _ = await tools.call(
        theirs,
        "pdf_pages",
        {"operation": "extract", "document_ids": [source], "pages": "1"},
    )

    text, is_error = await tools.call(
        mine,
        "pdf_stamp",
        {"artifact_id": _made(made), "kind": "watermark", "text": "X"},
    )

    assert is_error is True
    assert text == f"There is no artifact {_made(made)} in this workspace."


async def test_a_source_that_is_not_a_pdf_is_refused(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """The sentence names the source, so the model can pick another."""
    workspace_id = await tools.workspace()
    notes = _uploaded(engine, workspace_id, "Notes.txt", b"plain text")

    text, is_error = await tools.call(
        workspace_id, "pdf_form", {"action": "list", "document_id": notes}
    )

    assert is_error is True
    assert text == f'Source {notes} ("Notes.txt") is not a PDF.'


async def test_a_pdf_with_a_password_is_refused_in_a_sentence(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """Locked PDFs are common; the model must say why, not report a crash."""
    workspace_id = await tools.workspace()
    source = _uploaded(
        engine, workspace_id, "Locked.pdf", locked(numbered(1), user_password="pw")
    )

    text, is_error = await tools.call(
        workspace_id,
        "pdf_stamp",
        {"document_id": source, "kind": "footer", "text": "Draft"},
    )

    assert is_error is True
    assert text.startswith(f'Source {source} ("Locked.pdf") is protected by a password')


async def test_a_call_naming_the_wrong_number_of_inputs_says_so(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """Each operation's own needs are refused before any file is read."""
    workspace_id = await tools.workspace()
    source = _uploaded(engine, workspace_id, "A.pdf", numbered(2))

    merge_one, merge_is_error = await tools.call(
        workspace_id, "pdf_pages", {"operation": "merge", "document_ids": [source]}
    )
    rotate_no_angle, rotate_is_error = await tools.call(
        workspace_id, "pdf_pages", {"operation": "rotate", "document_ids": [source]}
    )

    assert merge_is_error and rotate_is_error
    assert "Merge needs at least two PDFs" in merge_one
    assert "angle" in rotate_no_angle


async def test_a_forms_fields_are_listed_then_filled_on_a_copy(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """The model fills by the names the list gives; the form itself stays blank."""
    workspace_id = await tools.workspace()
    application = form()
    source = _uploaded(engine, workspace_id, "Application.pdf", application)

    listed, list_is_error = await tools.call(
        workspace_id, "pdf_form", {"action": "list", "document_id": source}
    )
    filled, fill_is_error = await tools.call(
        workspace_id,
        "pdf_form",
        {
            "action": "fill",
            "document_id": source,
            "fields": {"name": "Asha Rao", "agree": True, "country": "Norway"},
            "flatten": True,
        },
    )

    assert list_is_error is False, listed
    assert listed.startswith(f'Source {source} ("Application.pdf") has 5 form fields')
    assert '- "country": dropdown on page 1, now "India"; options: India, Norway' in (
        listed
    )
    assert fill_is_error is False, filled
    assert "Filled 3 fields: name, agree, country." in filled
    assert "flattened" in filled
    _, data = _artifact(engine, _made(filled))
    assert "Asha Rao" in texts(data)[0]
    assert not pypdf.PdfReader(BytesIO(data)).get_fields()
    assert _original(workspace_id, source, "Application.pdf") == application


async def test_an_unknown_field_is_refused_and_nothing_is_made(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """A guessed field name must not leave a half-filled copy in Studio."""
    workspace_id = await tools.workspace()
    source = _uploaded(engine, workspace_id, "Application.pdf", form())

    text, is_error = await tools.call(
        workspace_id,
        "pdf_form",
        {"action": "fill", "document_id": source, "fields": {"surname": "Rao"}},
    )

    assert is_error is True
    assert 'This form has no field "surname".' in text
    with create_session_factory(engine)() as session:
        assert session.query(Artifact).count() == 0


async def test_a_form_with_long_lists_of_choices_is_listed_within_what_the_model_reads_whole(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """opencode moves a result past 50 KB into a folder every thread can read."""
    workspace_id = await tools.workspace()
    source = _uploaded(engine, workspace_id, "Survey.pdf", long_choices(60, 300))

    listed, is_error = await tools.call(
        workspace_id, "pdf_form", {"action": "list", "document_id": source}
    )

    assert is_error is False, listed
    assert len(listed.encode()) < 40_000
    assert '- "field 0": dropdown on page 1' in listed
    assert "and 280 more" in listed


async def test_pdfs_too_large_together_are_refused_before_any_is_read(
    tools: ToolEndpoint, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each PDF under the cap, many of them over it, would still fill memory."""
    workspace_id = await tools.workspace()
    data = numbered(3)
    ids = [_uploaded(engine, workspace_id, f"{n}.pdf", data) for n in range(3)]
    monkeypatch.setattr(opened_pdf, "MAX_BYTES", len(data) * 2)

    text, is_error = await tools.call(
        workspace_id, "pdf_pages", {"operation": "merge", "document_ids": ids}
    )

    assert is_error is True
    assert "together" in text
    with create_session_factory(engine)() as session:
        assert session.query(Artifact).count() == 0
