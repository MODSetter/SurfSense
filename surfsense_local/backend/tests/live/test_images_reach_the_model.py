"""Live case 2: a page preview the agent opens with `read` reaches Claude as an image.

Self-checking depends on it, and the path runs through opencode, SurfSense's
model endpoint and Anthropic's OpenAI-compatible API. When it does not arrive,
the requests the proxy recorded say where it was dropped.
"""

import json

import pytest

from tests.live.live_agent import LiveAgent, answer, steps

pytestmark = pytest.mark.live

CASE = "images-reach-the-model"
# What opencode puts in place of an image for a model it thinks cannot read one
# (provider/transform.ts, unsupportedParts).
_REPLACED = "does not support image input"


async def test_the_agent_sees_the_page_it_rendered(live: LiveAgent) -> None:
    """The page reaches Anthropic as an image, and the description matches it."""
    thread = await live.thread()

    frames = await live.turn(
        thread,
        "Make a one-page PDF titled 'Shape test' that shows one big green "
        "triangle filling most of the page, with the word ORBIT written large in "
        "black across its middle. Then open the page preview and tell me what you "
        "see on the page: the shape, its colour and the word.",
    )

    rendered = [
        s
        for s in steps(frames, "surfsense_render_document")
        if s["status"] == "completed"
    ]
    assert rendered, "the agent rendered no PDF"
    previews_read = [
        s for s in steps(frames, "read") if "previews" in json.dumps(s.get("input"))
    ]
    assert previews_read, "the agent never opened a page preview"
    sent = live.proxy.exchanges
    carried = [e for e in sent if e.images]
    replaced = [e for e in sent if _REPLACED in json.dumps(e.request["messages"])]
    assert carried, "no request to Anthropic carried the page image: " + (
        "opencode replaced it with its 'does not support image input' text, "
        "because the model SurfSense configures declares no image input"
        if replaced
        else "nothing in the requests stands in for it either"
    )
    seen = answer(frames).lower()
    assert "triangle" in seen and "green" in seen and "orbit" in seen, seen
