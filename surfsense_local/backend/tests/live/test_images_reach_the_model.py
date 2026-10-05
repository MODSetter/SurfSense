"""Live case 2: a rendered page reaches the model as an image, inline with the render's result.

Self-checking depends on it, and the path runs through the tool endpoint,
opencode's synthetic user message, SurfSense's model endpoint and the provider.
When it does not arrive, the requests the proxy recorded say where it was dropped.
"""

import json

import pytest

from tests.live.live_agent import LiveAgent, answer, steps
from tests.live.turn_renders import last_version, pages_sent_inline, previews_of

pytestmark = pytest.mark.live

CASE = "images-reach-the-model"
# What opencode puts in place of an image for a model it thinks cannot read one
# (provider/transform.ts, unsupportedParts).
_REPLACED = "does not support image input"


async def test_the_agent_sees_the_page_it_rendered(live: LiveAgent) -> None:
    """The page reaches the model inline, and the description matches it.

    Opening the preview with `read` does not count: it would hide a broken
    inline path whenever the model also opens the file.
    """
    thread = await live.thread()

    frames = await live.turn(
        thread,
        "Make a one-page PDF titled 'Shape test' that shows one big green "
        "triangle filling most of the page, with the word ORBIT written large in "
        "black across its middle. Then look at the page preview and tell me what "
        "you see on the page: the shape, its colour and the word.",
    )

    rendered = [
        s
        for s in steps(frames, "surfsense_render_document")
        if s["status"] == "completed"
    ]
    assert rendered, "the agent rendered no PDF"
    sent = live.proxy.exchanges
    carried = [e for e in sent if e.images]
    replaced = [e for e in sent if _REPLACED in json.dumps(e.request["messages"])]
    assert carried, "no request to the provider carried the page image: " + (
        "opencode replaced it with its 'does not support image input' text, "
        "because the model SurfSense configures declares no image input"
        if replaced
        else "nothing in the requests stands in for it either"
    )
    made = await last_version(live, frames, "turn 1")
    previews = previews_of(live, made)
    assert pages_sent_inline(sent, made, previews) == {1}, (
        f"page 1 of {made} never reached the model as the image the render attached"
    )
    seen = answer(frames).lower()
    assert "triangle" in seen and "green" in seen and "orbit" in seen, seen
