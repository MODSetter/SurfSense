"""Persist a Markdown deliverable as a first-class document."""

from __future__ import annotations

import logging
from dataclasses import asdict

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.artifacts import save_artifact
from app.db import shielded_async_session

from .thread_resolver import resolve_root_thread_id

logger = logging.getLogger(__name__)


def create_save_artifact_tool(workspace_id: int, thread_id: int | None = None):
    """Create the Markdown artifact tool with workspace dependencies injected."""

    @tool
    async def save_artifact_tool(
        title: str,
        content: str,
        runtime: ToolRuntime,
        description: str | None = None,
        document_id: int | None = None,
    ):
        """Save a Markdown deliverable, or revise an existing generated artifact.

        Use this for durable documents the user asked to keep, including
        summaries, reports, memos, guides, briefs, and other Markdown
        deliverables. Pass ``document_id`` only when revising that artifact.
        """
        del description
        root_thread_id = resolve_root_thread_id(runtime, thread_id)
        try:
            async with shielded_async_session() as session:
                saved = await save_artifact(
                    session,
                    workspace_id=workspace_id,
                    thread_id=root_thread_id,
                    tool_call_id=runtime.tool_call_id,
                    title=title,
                    markdown_representation=content,
                    files=[],
                    document_id=document_id,
                )
            return with_receipt(
                payload=asdict(saved),
                receipt=make_receipt(
                    route="deliverables",
                    type="artifact",
                    operation="generate",
                    status="success",
                    external_id=str(saved.document_id),
                    preview=saved.title,
                ),
                tool_call_id=runtime.tool_call_id,
            )
        except Exception as exc:
            error = str(exc)
            logger.exception("[save_artifact] %s", error)
            return with_receipt(
                payload={"status": "failed", "error": error},
                receipt=make_receipt(
                    route="deliverables",
                    type="artifact",
                    operation="generate",
                    status="failed",
                    error=error,
                ),
                tool_call_id=runtime.tool_call_id,
            )

    # Keep the public tool name frozen even though the Python symbol avoids
    # shadowing the service imported above.
    save_artifact_tool.name = "save_artifact"
    return save_artifact_tool
