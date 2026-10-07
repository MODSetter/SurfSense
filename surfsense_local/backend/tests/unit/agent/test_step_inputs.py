"""A step's inputs in the thread: every one its label reads, none of a long text's bulk."""

from typing import Any

import pytest

from modules.agent.agent_threads.replies import turn_reply
from modules.agent.agent_threads.steps import MAX_INPUT_CHARS, step_of

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
