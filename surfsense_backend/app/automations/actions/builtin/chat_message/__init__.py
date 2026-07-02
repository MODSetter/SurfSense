"""``chat_message`` action: post one turn into an existing chat thread.

Imports ``definition`` for its side-effect (self-registration on the actions
registry) and re-exports ``build_handler`` for direct consumers.
"""

from __future__ import annotations

from .factory import build_handler
from .params import ChatMessageActionParams

__all__ = ["ChatMessageActionParams", "build_handler"]

# Side-effect: register on the actions store.
from . import definition  # noqa: F401
