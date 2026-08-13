"""Authenticated artifact door: prompt -> artifact(s) via the deliverables subagent.

Runs the same engine chat uses (``run_deliverable_subagent``): mints a blank
``NewChatThread`` so the sandbox session key and artifact attribution get the int
thread id they require, resolves the workspace chat model, bills the chat-turn
credit seam, and returns the artifacts the subagent saved.
``ponytail:`` synchronous request; upgrade to 202 + poll/SSE with the async engine.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.run import (
    run_deliverable_subagent,
)
from app.auth.context import AuthContext
from app.capabilities.core.access.rate_limit import enforce_capability_rate_limit
from app.db import ChatVisibility, NewChatThread, Workspace, get_async_session
from app.sandbox import is_sandbox_enabled
from app.services.token_tracking_service import start_turn
from app.tasks.chat.streaming.flows.new_chat.auto_pin import resolve_initial_auto_pin
from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle
from app.tasks.chat.streaming.flows.shared.pre_stream_setup import get_chat_checkpointer
from app.tasks.chat.streaming.flows.shared.premium_quota import (
    finalize_credit,
    needs_credit_quota,
    release_credit,
    reserve_credit,
)
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access

logger = logging.getLogger(__name__)


class ArtifactGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    title: str | None = Field(default=None, max_length=200)


class ArtifactFileOut(BaseModel):
    file_id: int
    role: str
    filename: str
    mime_type: str
    size_bytes: int
    content_url: str


class ArtifactOut(BaseModel):
    artifact_id: int
    generation: int
    title: str
    files: list[ArtifactFileOut]


class ArtifactGenerationResponse(BaseModel):
    thread_id: int
    artifacts: list[ArtifactOut]
    message: str


def build_authenticated_artifact_router() -> APIRouter:
    router = APIRouter(tags=["artifacts-generation"])

    @router.post(
        "/workspaces/{workspace_id}/artifacts/generate",
        response_model=ArtifactGenerationResponse,
        name="artifacts:generate",
        dependencies=[Depends(enforce_capability_rate_limit)],
    )
    async def generate_artifact(
        workspace_id: int,
        payload: ArtifactGenerationRequest,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        await check_workspace_access(session, auth, workspace_id)
        if not is_sandbox_enabled():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Artifact generation is not enabled on this server.",
            )
        workspace = (
            (
                await session.execute(
                    select(Workspace).filter(Workspace.id == workspace_id)
                )
            )
            .scalars()
            .first()
        )
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
            )

        user_id = str(auth.user.id)

        thread = NewChatThread(
            workspace_id=workspace_id,
            created_by_id=auth.user.id,
            title=(payload.title or payload.prompt).strip()[:120] or "Artifact",
            visibility=ChatVisibility.PRIVATE,
            source="surfsense",
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        thread_id = thread.id

        pin = await resolve_initial_auto_pin(
            session,
            chat_id=thread_id,
            workspace_id=workspace_id,
            user_id=user_id,
            selected_llm_config_id=0,
            requires_image_input=False,
            requested_llm_config_id=0,
        )
        if pin.error is not None:
            _code, _kind, diagnostic = pin.error
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=diagnostic or "No chat model available for this workspace.",
            )
        llm, agent_config, llm_error = await load_llm_bundle(
            session, config_id=pin.llm_config_id, workspace_id=workspace_id
        )
        if llm_error or not llm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=llm_error or "Failed to load chat model.",
            )

        checkpointer = await get_chat_checkpointer()

        accumulator = start_turn()
        reservation = None
        if needs_credit_quota(agent_config, user_id):
            reservation = await reserve_credit(
                agent_config=agent_config, user_id=user_id
            )
            if not reservation.allowed:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Out of credits for artifact generation.",
                )

        try:
            run = await run_deliverable_subagent(
                session=session,
                workspace_id=workspace_id,
                thread_id=thread_id,
                prompt=payload.prompt,
                llm=llm,
                checkpointer=checkpointer,
            )
        except Exception:
            if reservation is not None:
                await release_credit(reservation=reservation, user_id=user_id)
            logger.exception("Artifact generation failed (workspace=%s)", workspace_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Artifact generation failed.",
            ) from None

        if reservation is not None:
            await finalize_credit(
                reservation=reservation, user_id=user_id, accumulator=accumulator
            )

        return ArtifactGenerationResponse(
            thread_id=thread_id,
            message=run.message,
            artifacts=[
                ArtifactOut(
                    artifact_id=a.artifact_id,
                    generation=a.generation,
                    title=a.title,
                    files=[
                        ArtifactFileOut(
                            file_id=f.file_id,
                            role=f.role,
                            filename=f.filename,
                            mime_type=f.mime_type,
                            size_bytes=f.size_bytes,
                            content_url=(
                                f"/api/v1/workspaces/{workspace_id}/artifacts/"
                                f"{a.artifact_id}/files/{f.file_id}/content"
                            ),
                        )
                        for f in a.files
                    ],
                )
                for a in run.artifacts
            ],
        )

    return router
