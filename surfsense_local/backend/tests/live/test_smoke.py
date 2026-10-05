"""Live case 1: one agent turn answers from the sources through SurfSense's search, and cites them."""

import pytest

from tests.live.live_agent import LiveAgent, steps

pytestmark = pytest.mark.live

CASE = "smoke"


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
    assert "16 November" in completed["text"], completed["text"]
    cited = [f for f in frames if f["type"] == "citations"]
    assert cited and cited[0]["items"], "the answer cites no passage"
    assert {item["document_id"] for item in cited[0]["items"]} == {note}
