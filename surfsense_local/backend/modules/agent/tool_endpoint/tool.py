"""What a tool is to the endpoint: its listing, how it runs, and how it refuses."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session


class ToolCallError(Exception):
    """A call the tool cannot carry out, said in a sentence the model can act on."""


@dataclass(frozen=True)
class Tool:
    """One tool: the listing opencode shows the model, and the work a call does.

    `run` takes the session, the workspace and the call's arguments, and returns
    the text the model reads; it runs off the event loop, in one transaction
    committed when it returns.
    """

    listing: dict[str, Any]
    run: Callable[[Session, int, dict[str, Any]], str]
    # Set for a tool that waits on another process: it commits its own short
    # transactions, since the write lock held while it waits would stall that process.
    waits: bool = False
