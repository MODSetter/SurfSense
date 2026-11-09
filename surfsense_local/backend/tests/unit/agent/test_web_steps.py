"""A web tool's step carries the hosts it was refused, so the thread can offer to allow them."""

from typing import Any

import pytest

from modules.agent.agent_threads.steps import step_of
from modules.agent.tool_endpoint.web_reach import refused_text

pytestmark = pytest.mark.unit


def tool_item(
    tool: str, *, error: str | None = None, output: str | None = None
) -> dict[str, Any]:
    """A tool call as an engine keeps it: a refusal as an error, else as its text."""
    state: dict[str, Any] = {"status": "error" if error else "completed", "input": {}}
    if error is not None:
        state["error"] = {"type": "tool.execution", "message": error}
    if output is not None:
        state["content"] = [{"type": "text", "text": output}]
    return {"id": "call_1", "name": tool, "state": state}


@pytest.mark.parametrize(
    ("tool", "purpose"),
    [
        ("surfsense_read_web_page", "web_page"),
        ("surfsense_read_youtube_transcript", "web_page"),
        ("surfsense_search_web", "web_search"),
    ],
)
def test_a_refused_web_step_names_its_hosts_and_the_question_to_ask(
    tool: str, purpose: str
) -> None:
    """The question a page's host and a search server's host are each asked with."""
    step = step_of(
        tool_item(tool, error=refused_text(["tides.example", "www.tides.example"]))
    )

    assert step["refused"] == {
        "hosts": ["tides.example", "www.tides.example"],
        "purpose": purpose,
    }


def test_a_refusal_kept_as_the_results_text_is_read_too() -> None:
    """An engine may keep an error result as text."""
    step = step_of(
        tool_item("surfsense_read_web_page", output=refused_text(["tides.example"]))
    )

    assert step["refused"]["hosts"] == ["tides.example"]


def test_a_web_step_that_failed_otherwise_offers_nothing() -> None:
    """A page that could not be read is no host to allow."""
    step = step_of(
        tool_item(
            "surfsense_read_web_page", error="This page no longer exists at this link."
        )
    )

    assert "refused" not in step


def test_another_tools_text_is_never_read_as_a_refusal() -> None:
    """Only the web tools say it."""
    step = step_of(
        tool_item("surfsense_search_sources", output=refused_text(["tides.example"]))
    )

    assert "refused" not in step
