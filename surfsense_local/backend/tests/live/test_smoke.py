"""Live case 1: one agent turn answers from the sources through SurfSense's search, and cites them."""

import re

import pytest

from tests.live.live_agent import LiveAgent, steps

pytestmark = pytest.mark.live

CASE = "smoke"
# Any common spelling: a sweep stops a model that fails smoke, and a spelling is no skill.
_MOVE_DAY = re.compile(
    r"\b16(?:th)?\.?(?:\s+of)?\s+Nov(?:ember)?\b"
    r"|\bNov(?:ember)?\.?\s+16(?:th)?\b"
    r"|\b2026-11-16\b|\b16[./]11[./]2026\b|\b11/16/2026\b",
    re.IGNORECASE,
)


async def test_the_agent_searches_the_sources_and_cites_a_passage(
    live: LiveAgent,
) -> None:
    """The answer comes from the note, through the search, with its passage cited."""
    note = await live.note(
        "Depot move plan",
        "The Bergen depot moves to the new Laksevag site on Monday 16 November "
        "2026. Trucks are re-routed from the old yard from 6:00 that morning, and "
        "the old yard closes for good on 20 November.",
    )
    await live.wait_ready(note)
    thread = await live.thread()

    frames = await live.turn(thread, "When does the Bergen depot move?")

    searches = steps(frames, "surfsense_search_sources")
    assert [s["status"] for s in searches if s["status"] == "completed"], searches
    (completed,) = [f for f in frames if f["type"] == "completed"]
    assert says_the_move_day(completed["text"]), completed["text"]
    cited = [f for f in frames if f["type"] == "citations"]
    assert cited and cited[0]["items"], "the answer cites no passage"
    assert {item["document_id"] for item in cited[0]["items"]} == {note}


def says_the_move_day(answer: str) -> bool:
    """16 November 2026, as "November 16th", "16. November", "2026-11-16" or the like."""
    return bool(_MOVE_DAY.search(answer))
