"""Tool-call policy hints and shared parameter types for knowledge-base tools."""

from __future__ import annotations

from typing import Annotated

from mcp.types import ToolAnnotations
from pydantic import Field

READ = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
DELETE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
)

DocumentId = Annotated[
    int,
    Field(
        description="Document id from surfsense_search_knowledge_base or "
        "surfsense_list_documents results."
    ),
]

DocumentTypes = Annotated[
    list[str] | None,
    Field(
        description="Restrict to these document types, e.g. "
        "['FILE', 'CRAWLED_URL', 'YOUTUBE_VIDEO']. Omit for all types."
    ),
]
