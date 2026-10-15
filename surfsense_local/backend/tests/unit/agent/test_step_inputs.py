"""A step's inputs in the thread: every one its label reads, none of a long text's bulk."""

from typing import Any

import pytest

from modules.agent.agent_threads.replies import turn_reply
from modules.agent.agent_threads.steps import (
    MAX_INPUT_CHARS,
    MAX_INPUT_ITEMS,
    step_of,
)

pytestmark = pytest.mark.unit

SCRIPT = "doc.add_paragraph('Revenue rose.')\n" * 400


def _step(tool: str, given: dict[str, Any]) -> dict[str, Any]:
    return step_of(
        {
            "id": "prt_1",
            "type": "tool",
            "tool": tool,
            "state": {"status": "running", "input": given},
        }
    )


def test_a_render_keeps_its_title_and_format_and_the_start_of_its_script() -> None:
    """The script the model wrote is kilobytes the label never shows."""
    shown = _step(
        "surfsense_render_document",
        {"title": "Client proposal", "format": "docx", "script": SCRIPT},
    )["input"]

    assert shown["title"] == "Client proposal"
    assert shown["format"] == "docx"
    assert len(SCRIPT) > 12_000
    assert shown["script"] == SCRIPT[:MAX_INPUT_CHARS] + "…"


def test_every_input_a_label_reads_survives() -> None:
    """The pdf tools' labels name their operation, kind and action; a list its count."""
    given = {
        "command": "ls",
        "pattern": "*.md",
        "query": "q3 revenue",
        "document_id": 12,
        "source_ids": [1, 2, 3],
        "operation": "rotate",
        "kind": "watermark",
        "action": "fill",
    }

    assert _step("surfsense_pdf_pages", given)["input"] == given


def test_a_path_is_never_cut_since_the_label_names_its_file() -> None:
    """The file's name is the end of its path."""
    path = "/workspace/" + "deeply/nested/" * 40 + "report.md"

    shown = _step("read", {"filePath": path, "path": path})["input"]

    assert shown == {"filePath": path, "path": path}


def test_a_revision_keeps_its_first_edits_each_cut_like_a_text() -> None:
    """A revision's operations are the new content itself, nested where a top-level cut never reached."""
    rows = [[f"Row {r} cell {c}" for c in range(10)] for r in range(200)]
    text = "A new paragraph of the proposal.\n" * 800
    operations = [
        {"op": "set_range", "sheet": "Q3", "range": "A1:J200", "values": rows},
        {"op": "insert_paragraphs", "quote": "Summary", "text": text},
    ]

    shown = _step(
        "surfsense_revise_document", {"artifact_id": 7, "operations": operations}
    )["input"]

    assert shown["artifact_id"] == 7
    cells, paragraphs = shown["operations"]
    assert cells["op"] == "set_range"
    assert cells["values"] == [*rows[:MAX_INPUT_ITEMS], "…"]
    assert paragraphs["op"] == "insert_paragraphs"
    assert paragraphs["text"] == text[:MAX_INPUT_CHARS] + "…"


def test_a_long_list_keeps_its_first_items_and_ids_stay_whole() -> None:
    """A label counts the sources a call names; the rest of a long list is bulk."""
    ids = list(range(1, 60))
    edits = [{"op": "delete_slide", "slide": n} for n in range(1, 60)]

    shown = _step(
        "surfsense_revise_document", {"source_ids": ids, "operations": edits}
    )["input"]

    assert shown["source_ids"] == ids
    assert shown["operations"] == [*edits[:MAX_INPUT_ITEMS], "…"]


def test_a_stored_reply_cuts_inputs_as_the_stream_does() -> None:
    """Reopening the thread reads back the same short inputs, not the whole file written."""
    content = "x" * 50_000
    messages = [
        {"info": {"id": "msg_u", "role": "user"}, "parts": []},
        {
            "info": {"id": "msg_a", "role": "assistant", "parentID": "msg_u"},
            "parts": [
                {
                    "id": "prt_w",
                    "type": "tool",
                    "tool": "write",
                    "state": {
                        "status": "completed",
                        "input": {"filePath": "/w/notes.md", "content": content},
                        "output": "Wrote file successfully.",
                    },
                }
            ],
        },
    ]

    (step,) = turn_reply(messages, "msg_u", [])["content"]["steps"]

    assert step["input"] == {
        "filePath": "/w/notes.md",
        "content": content[:MAX_INPUT_CHARS] + "…",
    }
