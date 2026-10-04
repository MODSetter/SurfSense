"""What a tool is to the endpoint: its listing, how it runs, and how it refuses."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from modules.agent.tool_endpoint.turn_scope import TurnScope


class ToolCallError(Exception):
    """A call the tool cannot carry out, said in a sentence the model can act on."""


@dataclass(frozen=True)
class Tool:
    """One tool: the listing opencode shows the model, and the work a call does.

    `run` takes the session, the calling turn's scope (its workspace and the
    sources it may use) and the call's arguments, and returns the text the model
    reads; it runs off the event loop, in one transaction committed when it returns.
    """

    listing: dict[str, Any]
    run: Callable[[Session, "TurnScope", dict[str, Any]], str]
    # Set for a tool that waits on another process or does slow file work: it
    # commits its own short transactions, since the write lock held meanwhile
    # would stall every other writer.
    waits: bool = False
