"""Inject this chat's generated artifacts into each deliverables invocation."""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import SystemMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime
from sqlalchemy import select

from app.db import Document, shielded_async_session
from app.file_storage.persistence.enums import DocumentFileKind
from app.file_storage.persistence.models import DocumentFile

from ..tools.thread_resolver import root_thread_id_from_config

logger = logging.getLogger(__name__)

_ROSTER_LIMIT = 10


class ArtifactRosterMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Tell a fresh deliverables subagent which artifacts this chat owns."""

    tools = ()

    def __init__(self, *, workspace_id: int) -> None:
        self.workspace_id = workspace_id

    async def abefore_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        thread_id = root_thread_id_from_config(get_config())
        if thread_id is None:
            return None

        try:
            async with shielded_async_session() as session:
                rows = (
                    await session.execute(
                        select(
                            Document.id,
                            Document.title,
                            DocumentFile.original_filename,
                        )
                        .outerjoin(
                            DocumentFile,
                            (DocumentFile.document_id == Document.id)
                            & (DocumentFile.kind == DocumentFileKind.GENERATED)
                            & (DocumentFile.role == "primary"),
                        )
                        .where(
                            Document.workspace_id == self.workspace_id,
                            Document.document_metadata["generated"]
                            .as_string()
                            == "true",
                            Document.document_metadata["thread_id"].as_string()
                            == str(thread_id),
                        )
                        .order_by(
                            Document.updated_at.desc().nullslast(),
                            Document.id.desc(),
                        )
                        .limit(_ROSTER_LIMIT)
                    )
                ).all()
        except Exception:
            logger.exception("Failed to load the deliverables artifact roster")
            return None

        if not rows:
            return None

        entries = "\n".join(
            f"- document_id={document_id}; title={title!r}; "
            f"filename={filename or '(Markdown artifact)'}"
            for document_id, title, filename in rows
        )
        roster = SystemMessage(
            content=(
                "<artifact_roster>\n"
                "Artifacts previously created in this chat, newest first:\n"
                f"{entries}\n"
                "</artifact_roster>"
            )
        )
        return {"messages": [roster, *(state.get("messages") or [])]}
