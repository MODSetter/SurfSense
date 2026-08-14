"""Invoke the deliverables subagent directly for one prompt.

The same engine chat drives through ``task(deliverables)``: compile the
deliverables spec and run its ReAct loop (sandbox skills -> verify_artifact ->
save_artifact). Doors supply the workspace, an int thread id (sandbox key +
artifact attribution), the resolved chat model, and a checkpointer.
"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.chat.multi_agent_chat.shared.feature_flags import get_flags
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.agent import (
    build_subagent as build_deliverables_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.shared.invocation import (
    DEFAULT_SUBAGENT_RECURSION_LIMIT,
)
from app.artifacts.persistence import Artifact, ArtifactFileRole
from app.db import Document

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliverableFile:
    file_id: int
    role: str
    filename: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True)
class DeliverableArtifact:
    artifact_id: int
    generation: int
    title: str
    files: list[DeliverableFile]


@dataclass(frozen=True)
class DeliverableRunResult:
    artifacts: list[DeliverableArtifact]
    message: str


def _artifact_ids_from_messages(messages: list[Any]) -> list[int]:
    """Every ``artifact_id`` the run touched, in first-seen order.

    Tools ship heterogeneous JSON ToolMessage receipts: ``save_artifact`` uses
    ``artifact_id`` + ``files`` + ``generation``; the image tool uses
    ``artifact_id`` + an ``image-artifact-N`` payload with no files. Rather than
    parse each shape, collect the ids and hydrate the real files from the DB.
    """
    ids: list[int] = []
    seen: set[int] = set()
    for msg in messages:
        if not isinstance(msg, ToolMessage) or not isinstance(msg.content, str):
            continue
        try:
            payload = json.loads(msg.content)
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        artifact_id = payload.get("artifact_id")
        if isinstance(artifact_id, int) and artifact_id not in seen:
            seen.add(artifact_id)
            ids.append(artifact_id)
    return ids


async def _hydrate_artifacts(
    session: AsyncSession, workspace_id: int, artifact_ids: list[int]
) -> list[DeliverableArtifact]:
    """Load the run's artifacts and their visible files from the DB (source of truth)."""
    if not artifact_ids:
        return []
    rows = (
        await session.execute(
            select(Artifact, Document)
            .join(Document, Artifact.document_id == Document.id)
            .options(selectinload(Artifact.files))
            .where(
                Artifact.id.in_(artifact_ids),
                Artifact.workspace_id == workspace_id,
            )
        )
    ).all()
    out: list[DeliverableArtifact] = []
    for artifact, document in rows:
        files = sorted(
            (f for f in artifact.files if f.role is not ArtifactFileRole.SOURCE),
            key=lambda f: (f.role is not ArtifactFileRole.PRIMARY, f.id),
        )
        out.append(
            DeliverableArtifact(
                artifact_id=artifact.id,
                generation=artifact.generation,
                title=document.title or "",
                files=[
                    DeliverableFile(
                        file_id=f.id,
                        role=f.role.value,
                        filename=f.original_filename or "",
                        mime_type=f.mime_type or "application/octet-stream",
                        size_bytes=f.size_bytes or 0,
                    )
                    for f in files
                ],
            )
        )
    return out


def _final_text(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = msg.content
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ).strip()
            if text:
                return text
    return ""


async def run_deliverable_subagent(
    *,
    session: AsyncSession,
    workspace_id: int,
    thread_id: int,
    prompt: str,
    llm: BaseChatModel,
    checkpointer: Any,
    created_by_id: str | None = None,
    image_gen_model_id_override: int | None = None,
) -> DeliverableRunResult:
    """Compile the deliverables subagent and run it against ``prompt`` once."""
    dependencies: dict[str, Any] = {
        "workspace_id": workspace_id,
        "db_session": session,
        "flags": get_flags(),
        "llm": llm,
        "image_gen_model_id_override": image_gen_model_id_override,
    }
    spec = build_deliverables_subagent(dependencies=dependencies, model=llm).spec
    agent = create_agent(
        spec["model"],
        system_prompt=spec["system_prompt"],
        tools=spec["tools"],
        middleware=spec.get("middleware", []),
        name=spec["name"],
        checkpointer=checkpointer,
    )
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": DEFAULT_SUBAGENT_RECURSION_LIMIT,
    }
    from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence import (
        commit_turn_working_copy,
    )

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=prompt)]}, config=config
        )
        await commit_turn_working_copy(
            workspace_id=workspace_id,
            thread_id=thread_id,
            created_by_id=created_by_id,
            llm=llm,
        )
        messages = result.get("messages", []) if isinstance(result, dict) else []
        return DeliverableRunResult(
            artifacts=await _hydrate_artifacts(
                session, workspace_id, _artifact_ids_from_messages(messages)
            ),
            message=_final_text(messages),
        )
    finally:
        with contextlib.suppress(Exception):
            from app.sandbox.registry import get_registry

            await (await get_registry()).terminate(thread_id)
