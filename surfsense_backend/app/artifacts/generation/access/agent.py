"""The agent door: one LangChain tool per generator, over the shared pipeline.

Each tool runs the same adapter as the REST door — build an authenticated
context, run the generic pipeline, persist an Artifact — and returns the
kind's own receipt/``Command`` shape via ``render_success``.
"""

from __future__ import annotations

import logging

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from sqlalchemy import select

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.thread_resolver import (
    resolve_root_thread_id,
)
from app.artifacts.generation.core.context import AuthenticatedContext, generate
from app.artifacts.generation.core.registry import ArtifactGenerator, all_generators
from app.artifacts.generation.core.result import ArtifactRef
from app.db import Workspace, shielded_async_session
from app.services.billable_calls import QuotaInsufficientError

logger = logging.getLogger(__name__)


def build_artifact_tools(
    *, workspace_id: int, image_gen_model_id_override: int | None = None
) -> list[BaseTool]:
    """One tool per registered generator."""
    return [
        build_artifact_tool(
            gen,
            workspace_id=workspace_id,
            image_gen_model_id_override=image_gen_model_id_override,
        )
        for gen in all_generators()
    ]


def build_artifact_tool(
    gen: ArtifactGenerator,
    *,
    workspace_id: int,
    image_gen_model_id_override: int | None = None,
) -> BaseTool:
    input_model = gen.input_schema

    async def _run(runtime: ToolRuntime, **kwargs: object) -> Command:
        req = input_model(**kwargs)

        def _failed(message: str) -> Command:
            from app.agents.chat.multi_agent_chat.shared.receipts.command import (
                with_receipt,
            )
            from app.agents.chat.multi_agent_chat.shared.receipts.receipt import (
                make_receipt,
            )

            return with_receipt(
                payload={"error": message},
                receipt=make_receipt(
                    route=gen.receipt_route,
                    type=gen.receipt_type,
                    operation="generate",
                    status="failed",
                    preview=gen.preview(req),
                    error=message,
                ),
                tool_call_id=runtime.tool_call_id,
            )

        try:
            async with shielded_async_session() as session:
                workspace = (
                    await session.execute(
                        select(Workspace).filter(Workspace.id == workspace_id)
                    )
                ).scalars().first()
                if not workspace:
                    return _failed("Workspace not found")

                ctx = AuthenticatedContext(
                    session,
                    workspace,
                    image_gen_model_id_override=image_gen_model_id_override,
                    thread_id=resolve_root_thread_id(runtime),
                    tool_call_id=runtime.tool_call_id,
                    committed_by_turn=True,
                )
                result = await generate(gen, ctx, req)
            assert isinstance(result, ArtifactRef)
            return gen.render_success(result, req, runtime.tool_call_id)

        except QuotaInsufficientError:
            return _failed(
                f"Out of credits for {gen.kind} generation. Purchase additional "
                "credits or switch to a free model."
            )
        except gen.user_facing_errors as exc:
            return _failed(str(exc))
        except Exception as exc:
            logger.exception("%s generation failed in tool", gen.kind)
            return _failed(f"{gen.kind} generation failed: {exc!s}")

    _run.__annotations__["runtime"] = ToolRuntime

    return StructuredTool.from_function(
        coroutine=_run,
        name=gen.tool_name,
        description=gen.tool_description,
        args_schema=input_model,
    )
