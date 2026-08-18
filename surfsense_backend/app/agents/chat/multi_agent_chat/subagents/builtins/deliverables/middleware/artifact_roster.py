"""Inject this chat's generated artifacts into each deliverables invocation."""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import SystemMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime
from sqlalchemy import case, select

from app.artifacts.persistence import Artifact, ArtifactFile, ArtifactFileRole
from app.db import Document, shielded_async_session

from ..tools.thread_resolver import root_thread_id_from_config

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
        mentioned_ids = {
            artifact_id
            for artifact_id in state.get("mentioned_artifact_ids", [])
            if isinstance(artifact_id, int) and artifact_id > 0
        }
        ordering = []
        if mentioned_ids:
            ordering.append(case((Artifact.id.in_(mentioned_ids), 0), else_=1))
        ordering.extend([Artifact.updated_at.desc().nullslast(), Artifact.id.desc()])

        async with shielded_async_session() as session:
            rows = (
                await session.execute(
                    select(
                        Artifact.id,
                        Artifact.generation,
                        Artifact.format,
                        Document.title,
                        ArtifactFile.original_filename,
                    )
                    .join(Document, Artifact.document_id == Document.id)
                    .outerjoin(
                        ArtifactFile,
                        (ArtifactFile.artifact_id == Artifact.id)
                        & (ArtifactFile.role == ArtifactFileRole.PRIMARY),
                    )
                    .where(
                        Artifact.workspace_id == self.workspace_id,
                        Artifact.thread_id == thread_id,
                    )
                    .order_by(*ordering)
                    .limit(_ROSTER_LIMIT + len(mentioned_ids))
                )
            ).all()

        if not rows:
            return None

        entries = "\n".join(
            f"- artifact_id={artifact_id}; generation={generation}; "
            f"format={artifact_format}; title={title!r}; "
            f"filename={filename or '(Markdown artifact)'}"
            for artifact_id, generation, artifact_format, title, filename in rows
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
