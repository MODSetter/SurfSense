"""The read tool over a revised copy: its text as it reads now, with its changes and comments."""

import re
import zipfile
from io import BytesIO

import pytest

from modules.source_scope.schemas import SourceScope
from tests.integration.agent.tool_endpoint_client import ToolEndpoint
from tests.integration.artifacts.revised_copies.source_files import (
    add_source,
    contract_docx,
    pitch_pptx,
    pricing_xlsx,
)
from tests.integration.worker.conftest import stub_model  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("stub_model", "model_reads_images", "studio_worker"),
]

TOOL = "read_document"
TERMINATION = "Either party may terminate this agreement with 60 days notice."
# Another reviewer's redline already in the user's file: 60 struck, 90 inserted.
OTHERS_REDLINE = (
    '<w:r><w:t xml:space="preserve">Either party may terminate this agreement with '
    '</w:t></w:r><w:del w:id="901" w:author="Dana Reyes" w:date="2026-09-01T00:00:00Z">'
    "<w:r><w:delText>60</w:delText></w:r></w:del>"
    '<w:ins w:id="902" w:author="Dana Reyes" w:date="2026-09-01T00:00:00Z">'
    "<w:r><w:t>90</w:t></w:r></w:ins>"
    '<w:r><w:t xml:space="preserve"> days notice.</w:t></w:r>'
)


def _redlined_contract() -> bytes:
    source = BytesIO(contract_docx())
    out = BytesIO()
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(out, "w") as after:
        for item in before.infolist():
            data = before.read(item.filename)
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                plain = f"<w:r><w:t>{TERMINATION}</w:t></w:r>"
                assert plain in xml
                data = xml.replace(plain, OTHERS_REDLINE).encode("utf-8")
            after.writestr(item, data)
    return out.getvalue()


async def _revised(
    tools: ToolEndpoint, name: str, data: bytes, operations: list[dict]
) -> tuple[int, int]:
    workspace_id = await tools.workspace()
    with tools.sessions() as session:
        source_id = add_source(session, workspace_id, name, data)
    text, is_error = await tools.call(
        workspace_id,
        "revise_document",
        {"document_id": source_id, "operations": operations},
    )
    assert is_error is False, text
    return workspace_id, int(text.split(",")[0].removeprefix("Rendered artifact "))


async def test_a_revised_word_copy_reads_with_every_author_s_changes_and_comments(
    tools: ToolEndpoint,
) -> None:
    """The rehearsal's read of a redline answered that a Studio document keeps no script."""
    workspace_id, artifact_id = await _revised(
        tools,
        "MSA_Acme.docx",
        _redlined_contract(),
        [
            {
                "op": "replace_text",
                "quote": "30 days",
                "text": "45 days",
                "comment": "The user asked for 45 days.",
            },
            {
                "op": "add_comment",
                "quote": "terminate this agreement",
                "text": "Check this notice period.",
                "internal": True,
            },
        ],
    )

    text, is_error = await tools.call(workspace_id, TOOL, {"artifact_id": artifact_id})

    assert is_error is False, text
    assert "keeps no script" not in text
    assert text.splitlines()[0].startswith(
        f'Artifact {artifact_id}, version 1 of the revised copy of "MSA_Acme.docx", '
        "is a Word document"
    )
    assert "4 tracked changes and 2 comments" in text
    assert f"surfsense_revise_document with artifact_id {artifact_id}" in text
    assert "Master Services Agreement" in text
    assert re.search(
        r'within <del author="SurfSense">30</del><ins author="SurfSense">45</ins>'
        r"\[comment \d+\] days of",
        text,
    ), text
    assert (
        'with <del author="Dana Reyes">60</del><ins author="Dana Reyes">90</ins> '
        "days notice." in text
    )
    assert re.search(
        r'Comment \d+ by SurfSense on "45": The user asked for 45 days\.', text
    ), text
    assert re.search(
        r'Comment \d+ by SurfSense, internal, on "terminate this agreement": '
        r"Check this notice period\.",
        text,
    ), text


async def test_a_revised_deck_reads_as_each_slide_s_text(tools: ToolEndpoint) -> None:
    """A deck keeps no tracked changes: its slides read as they are now."""
    workspace_id, artifact_id = await _revised(
        tools,
        "Pitch.pptx",
        pitch_pptx(),
        [{"op": "replace_text", "slide": 2, "quote": "Pricing", "text": "Prices"}],
    )

    text, is_error = await tools.call(workspace_id, TOOL, {"artifact_id": artifact_id})

    assert is_error is False, text
    assert text.splitlines()[0].startswith(
        f'Artifact {artifact_id}, version 1 of the revised copy of "Pitch.pptx", '
        "is a PowerPoint deck"
    )
    assert "## Slide 1: Halvorsen Freight" in text
    assert "## Slide 2: Prices" in text
    assert "1 edit, made in place" in text
    assert f"surfsense_revise_document with artifact_id {artifact_id}" in text


async def test_a_revised_workbook_counts_its_edits(tools: ToolEndpoint) -> None:
    """Excel keeps no tracked changes either, so the count is of the edits made."""
    workspace_id, artifact_id = await _revised(
        tools,
        "Pricing.xlsx",
        pricing_xlsx(),
        [
            {"op": "set_cell", "sheet": "Pricing", "cell": "B2", "value": 15000},
            {"op": "set_cell", "sheet": "Pricing", "cell": "B3", "value": 31000},
        ],
    )

    text, is_error = await tools.call(workspace_id, TOOL, {"artifact_id": artifact_id})

    assert is_error is False, text
    assert "2 edits, made in place" in text
    assert "B2 = 15000" in text


async def test_a_revised_copy_is_read_whatever_sources_the_turn_ticks(
    tools: ToolEndpoint,
) -> None:
    """A revised copy is the agent's output, so a later turn reads it like any artifact."""
    workspace_id, artifact_id = await _revised(
        tools,
        "MSA_Acme.docx",
        contract_docx(),
        [{"op": "replace_text", "quote": "30 days", "text": "45 days"}],
    )

    text, is_error = await tools.call(
        workspace_id,
        TOOL,
        {"artifact_id": artifact_id},
        thread=tools.thread(workspace_id, SourceScope(document_ids=[])),
    )

    assert is_error is False, text
    assert '<ins author="SurfSense">45</ins> days' in text
