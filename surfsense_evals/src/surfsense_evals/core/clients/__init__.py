"""HTTP clients for the SurfSense API. All share one ``httpx.AsyncClient``."""

from __future__ import annotations

from .documents import DocumentsClient
from .new_chat import NewChatClient, StreamedAnswer
from .search_space import SearchSpaceClient

__all__ = [
    "DocumentsClient",
    "NewChatClient",
    "SearchSpaceClient",
    "StreamedAnswer",
]
