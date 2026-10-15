"""An optional id sent as 0 is taken as left out, as OpenAI's models send every field."""

import pytest

from modules.agent.tool_endpoint.offered_tools import TOOLS, without_placeholder_ids

pytestmark = pytest.mark.unit

RENDER = TOOLS["render_document"].listing


def test_optional_ids_of_zero_are_left_out() -> None:
    """A render with no document to continue and no template, as GPT-4.1 and o3 sent it."""
    sent = {
        "title": "Brief",
        "format": "pdf",
        "script": "x",
        "artifact_id": 0,
        "template_source_id": 0,
        "images": [],
    }

    assert without_placeholder_ids(RENDER, sent) == {
        "title": "Brief",
        "format": "pdf",
        "script": "x",
        "images": [],
    }


def test_a_real_id_is_kept() -> None:
    """Only 0 names nothing; ids count from 1."""
    sent = {
        "title": "Brief",
        "format": "pdf",
        "script": "x",
        "artifact_id": 7,
        "template_source_id": 3,
    }

    assert without_placeholder_ids(RENDER, sent) == sent


def test_a_required_id_of_zero_is_left_for_the_tool_to_refuse() -> None:
    """A tool that needs an id still says which one is wrong."""
    listing = {
        "name": "t",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": {"type": "integer"}},
            "required": ["document_id"],
        },
    }

    assert without_placeholder_ids(listing, {"document_id": 0}) == {"document_id": 0}


def test_false_and_other_fields_are_untouched() -> None:
    """False equals 0 in Python, but it is not an id; a count of 0 is a real value."""
    listing = {
        "name": "t",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "integer"},
                "pages": {"type": "integer"},
            },
        },
    }
    sent = {"artifact_id": False, "pages": 0}

    assert without_placeholder_ids(listing, sent) == sent


def test_every_tool_s_optional_ids_are_integers() -> None:
    """The rule reads each listing; an id typed another way would slip past it."""
    for tool in TOOLS.values():
        schema = tool.listing.get("inputSchema") or {}
        for name, spec in (schema.get("properties") or {}).items():
            if name.endswith("_id"):
                assert spec.get("type") == "integer", (tool.listing["name"], name)
