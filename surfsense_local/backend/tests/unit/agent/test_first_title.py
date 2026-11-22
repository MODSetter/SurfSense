"""An agent thread's name from its first message, as long as a chat's own title may be."""

import pytest

from modules.agent.agent_threads.turn import first_title
from modules.chat.models import ChatThread

pytestmark = pytest.mark.unit


def test_keeps_up_to_100_characters_of_the_first_message() -> None:
    """A long first message is cut at 100 characters, its last one an ellipsis."""
    text = "Explain how a rate limiter works with an interactive figure " * 3

    title = first_title(ChatThread(title="New chat"), text)

    assert title is not None
    assert len(title) == 100
    assert title.endswith("…")
    assert title.startswith(
        "Explain how a rate limiter works with an interactive figure Explain"
    )


def test_a_message_that_fits_is_the_whole_title() -> None:
    """A first message that fits is the title as it is, with no ellipsis."""
    text = "Show how a load balancer works as a switchyard, with an interactive figure"

    assert first_title(ChatThread(title="New chat"), text) == text
