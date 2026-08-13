"""Invoke the deliverables subagent directly for one prompt.

The same engine chat drives through ``task(deliverables)``: compile the
deliverables spec and run its ReAct loop (sandbox skills -> verify_artifact ->
save_artifact). Doors supply the workspace, an int thread id (sandbox key +
artifact attribution), the resolved chat model, and a checkpointer.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.feature_flags import get_flags
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.agent import (
    build_subagent as build_deliverables_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.shared.invocation import (
    DEFAULT_SUBAGENT_RECURSION_LIMIT,
)

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


def _file_from(entry: dict[str, Any]) -> DeliverableFile | None:
    try:
        return DeliverableFile(
            file_id=int(entry["file_id"]),
            role=str(entry.get("role", "")),
            filename=str(entry.get("filename", "")),
            mime_type=str(entry.get("mime_type", "")),
            size_bytes=int(entry.get("size_bytes", 0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _artifacts_from_messages(messages: list[Any]) -> list[DeliverableArtifact]:
    """Pull saved artifacts out of the run's ``save_artifact`` tool results.

    ``save_artifact`` ships ``asdict(ArtifactSaved)`` as JSON ToolMessage
    content (``artifact_id`` + ``generation`` + ``files``); failure payloads
    and other tools' receipts lack that shape and are skipped. Later
    generations of the same artifact (a revision within one run) win.
    """
    by_id: dict[int, DeliverableArtifact] = {}
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
        files = payload.get("files")
        if (
            not isinstance(artifact_id, int)
            or not isinstance(files, list)
            or "generation" not in payload
        ):
            continue
        parsed_files = [
            f for f in (_file_from(e) for e in files if isinstance(e, dict)) if f
        ]
        by_id[artifact_id] = DeliverableArtifact(
            artifact_id=artifact_id,
            generation=int(payload.get("generation") or 1),
            title=str(payload.get("title") or ""),
            files=parsed_files,
        )
    return list(by_id.values())


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
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=prompt)]}, config=config
    )
    messages = result.get("messages", []) if isinstance(result, dict) else []
    return DeliverableRunResult(
        artifacts=_artifacts_from_messages(messages),
        message=_final_text(messages),
    )
