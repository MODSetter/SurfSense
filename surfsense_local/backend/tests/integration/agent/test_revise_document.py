"""The revise tool as opencode's MCP client calls it: a revised copy of a selected source file."""

import pytest

from modules.source_scope.schemas import SourceScope
from tests.integration.agent.tool_endpoint_client import ToolEndpoint
from tests.integration.artifacts.revised_copies.source_files import (
    add_source,
    contract_docx,
    pricing_xlsx,
    source_path,
)
from tests.integration.worker.conftest import stub_model  # noqa: F401
from tests.office_stand_in import office_on

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("stub_model", "model_reads_images"),
]

NAME = "MSA_Acme.docx"
TOOL = "revise_document"
REPLACE = {"op": "replace_text", "quote": "within 30 days", "text": "within 45 days"}
MISSING = {"op": "replace_text", "quote": "within 31 days", "text": "within 45 days"}


def _source(tools: ToolEndpoint, workspace_id: int, name: str = NAME) -> int:
    data = pricing_xlsx() if name.endswith(".xlsx") else contract_docx()
    if name.endswith(".pdf"):
        data = b"%PDF-1.7\n"
    with tools.sessions() as session:
        return add_source(session, workspace_id, name, data)


def _artifact_id(text: str) -> int:
    return int(text.split(",")[0].removeprefix("Rendered artifact "))


async def _listed(tools: ToolEndpoint, workspace_id: int) -> list[dict]:
    reply = await tools.client.get(f"/workspaces/{workspace_id}/artifacts")
    return reply.json()


async def test_revising_a_source_makes_version_1_and_says_what_changed(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """The model learns the copy's id and version, each operation's outcome and the counts."""
    workspace_id = await tools.workspace()
    source_id = _source(tools, workspace_id)
    original = source_path(workspace_id, source_id, NAME).read_bytes()

    text, is_error = await tools.call(
        workspace_id, TOOL, {"document_id": source_id, "operations": [REPLACE]}
    )

    assert is_error is False, text
    lines = text.splitlines()
    artifact_id = _artifact_id(text)
    assert lines[0] == f"Rendered artifact {artifact_id}, version 1: MSA_Acme (revised)"
    assert lines[1].startswith(
        f"Revised copy of source {source_id} ({NAME}), version 1. "
        "1 of 1 operations applied; "
    )
    assert lines[1].endswith(" tracked changes, 0 comments.")
    assert lines[2] == "#0 replace_text: applied."
    assert "within 45 days" in text
    assert f"revise with artifact_id {artifact_id}" in text
    assert source_path(workspace_id, source_id, NAME).read_bytes() == original


async def test_revising_the_copy_again_makes_its_next_version(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """artifact_id adds the edits on top of the copy's newest version."""
    workspace_id = await tools.workspace()
    source_id = _source(tools, workspace_id)
    first, _ = await tools.call(
        workspace_id, TOOL, {"document_id": source_id, "operations": [REPLACE]}
    )

    text, is_error = await tools.call(
        workspace_id,
        TOOL,
        {
            "artifact_id": _artifact_id(first),
            "operations": [
                {"op": "add_comment", "quote": "60 days", "text": "Ask for 90."}
            ],
        },
    )

    assert is_error is False, text
    assert ", version 2 from version 1. 1 of 1 operations applied;" in text
    assert text.splitlines()[1].endswith(", 1 comment.")


async def test_a_refused_operation_saves_nothing_and_says_which_to_fix(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """All or nothing: the refusal names the operation and makes no version."""
    workspace_id = await tools.workspace()
    source_id = _source(tools, workspace_id)

    text, is_error = await tools.call(
        workspace_id,
        TOOL,
        {"document_id": source_id, "operations": [REPLACE, MISSING]},
    )

    assert is_error is True
    assert text.startswith("Nothing was saved.\n")
    assert "#1 replace_text refused (QUOTE_NOT_FOUND)" in text
    assert "#0 replace_text skipped (BATCH_REFUSED)" in text
    assert text.endswith("Fix the refused operation and send all 2 again.")
    assert await _listed(tools, workspace_id) == []


async def test_refusals_do_not_count_toward_the_three_failures_stop(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """The model that saved nothing still has its tries left to get the quote right."""
    workspace_id = await tools.workspace()
    source_id = _source(tools, workspace_id)
    for _ in range(3):
        await tools.call(
            workspace_id, TOOL, {"document_id": source_id, "operations": [MISSING]}
        )

    text, is_error = await tools.call(
        workspace_id, TOOL, {"document_id": source_id, "operations": [REPLACE]}
    )

    assert is_error is False, text


async def test_a_source_the_user_did_not_select_is_refused(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """A source is revised only when the user ticked it for this chat."""
    workspace_id = await tools.workspace()
    ticked = _source(tools, workspace_id, "Other.docx")
    unticked = _source(tools, workspace_id)

    text, is_error = await tools.call(
        workspace_id,
        TOOL,
        {"document_id": unticked, "operations": [REPLACE]},
        thread=tools.thread(workspace_id, SourceScope(document_ids=[ticked])),
    )

    assert is_error is True
    assert f"Source {unticked} is not selected for this request." in text


@pytest.mark.parametrize(
    ("ids", "said"),
    [
        ({}, "one of them, not both"),
        ({"document_id": 1, "artifact_id": 2}, "one of them, not both"),
    ],
)
async def test_one_id_is_needed(
    tools: ToolEndpoint, ids: dict, said: str, studio_worker: None
) -> None:
    """A source or a revised copy, never both and never neither."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id, TOOL, {**ids, "operations": [REPLACE]}
    )

    assert is_error is True
    assert said in text


async def test_a_file_of_another_kind_is_refused_naming_the_kinds_revised(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """The refusal says which files can be revised."""
    workspace_id = await tools.workspace()
    source_id = _source(tools, workspace_id, "Scan.pdf")

    text, is_error = await tools.call(
        workspace_id, TOOL, {"document_id": source_id, "operations": [REPLACE]}
    )

    assert is_error is True
    assert "SurfSense revises .docx, .xlsx, .xlsm and .pptx files." in text


async def test_revising_the_same_source_again_points_at_its_copy(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """Weaker models leave the id of what they made out of the next edit."""
    workspace_id = await tools.workspace()
    source_id = _source(tools, workspace_id)
    first, _ = await tools.call(
        workspace_id, TOOL, {"document_id": source_id, "operations": [REPLACE]}
    )

    text, is_error = await tools.call(
        workspace_id, TOOL, {"document_id": source_id, "operations": [REPLACE]}
    )

    assert is_error is True
    assert f"pass artifact_id {_artifact_id(first)}" in text


async def test_an_artifact_that_is_not_a_revised_copy_is_refused(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """An id that names no revised copy in this workspace is refused."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id, TOOL, {"artifact_id": 999, "operations": [REPLACE]}
    )

    assert is_error is True
    assert "There is no artifact 999 in this workspace." in text


async def test_a_workbook_revision_answers_with_its_summary(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """A workbook has no pages, so its summary is what the model checks."""
    workspace_id = await tools.workspace()
    source_id = _source(tools, workspace_id, "Pricing.xlsx")

    text, is_error = await tools.call(
        workspace_id,
        TOOL,
        {
            "document_id": source_id,
            "operations": [
                {"op": "set_cell", "sheet": "Pricing", "cell": "B2", "value": 15000}
            ],
        },
    )

    assert is_error is False, text
    assert text.splitlines()[1].endswith("1 of 1 operations applied.")
    assert "Its summary:" in text
    assert 'Sheet "Pricing"' in text


async def test_with_office_support_a_word_copy_s_previews_name_libreoffice(
    tools: ToolEndpoint, studio_worker: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LibreOffice drew the pages, so the result names it, not the in-app viewer's gaps."""
    office_on(monkeypatch, pages=2)
    workspace_id = await tools.workspace()
    source_id = _source(tools, workspace_id)

    text, images, is_error = await tools.call_content(
        workspace_id, TOOL, {"document_id": source_id, "operations": [REPLACE]}
    )

    assert is_error is False, text
    assert len(images) == 2
    assert "Drawn by LibreOffice 26.8.1" in text
    assert "SurfSense's Word viewer" not in text
    assert "tracked changes" in text
