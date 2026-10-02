"""The citations an agent reply may make: the passages its session's searches returned, and no others."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.passage_label import labelled_chunks
from modules.agent.tool_endpoint.registration import SERVER
from modules.agent.tool_endpoint.search_sources import LISTING
from modules.chat.prompt import Citation
from modules.chunks.models import Chunk
from modules.documents.models import Document

# As opencode names it: the server it was registered under, then the tool.
SEARCH_TOOL = f"{SERVER}_{LISTING['name']}"


def searched_chunks(messages: list[dict[str, Any]]) -> set[int]:
    """Every chunk the session's searches have labelled so far."""
    return {
        chunk_id
        for message in messages
        for part in message["parts"]
        if part.get("type") == "tool"
        and part.get("tool") == SEARCH_TOOL
        and part.get("state", {}).get("status") == "completed"
        for chunk_id in labelled_chunks(part["state"].get("output") or "")
    }


def load_citations(
    session: Session, workspace_id: int, chunk_ids: set[int]
) -> list[Citation]:
    """Where each chunk came from, for those still in the workspace.

    A chunk is cited by its own id, the label the search gave it, so `source_id`
    is the chunk id.
    """
    if not chunk_ids:
        return []
    rows = session.execute(
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.start_line,
            Chunk.end_line,
            Document.title,
        )
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(chunk_ids), Document.workspace_id == workspace_id)
    ).all()
    return [
        Citation(
            row.id, row.id, row.document_id, row.start_line, row.end_line, row.title
        )
        for row in rows
    ]
