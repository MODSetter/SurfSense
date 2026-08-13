"""The authenticated developer door: one typed POST per generator.

Same adapter as the agent door — build an authenticated context, run the
generic pipeline, persist an Artifact — but returns the kind's typed REST
response. Mirrors ``build_capabilities_router``.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.generation.core.context import AuthenticatedContext, generate
from app.artifacts.generation.core.registry import ArtifactGenerator, all_generators
from app.auth.context import AuthContext
from app.capabilities.core.access.rate_limit import enforce_capability_rate_limit
from app.db import Workspace, get_async_session
from app.services.billable_calls import QuotaInsufficientError
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access

logger = logging.getLogger(__name__)


def build_artifact_router() -> APIRouter:
    """One typed route per registered generator."""
    router = APIRouter(tags=["artifacts-generation"])
    for gen in all_generators():
        _register(router, gen)
    return router


def _register(router: APIRouter, gen: ArtifactGenerator) -> None:
    input_model = gen.input_schema

    async def endpoint(
        workspace_id: int,
        payload: input_model,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        await check_workspace_access(session, auth, workspace_id)
        workspace = (
            await session.execute(
                select(Workspace).filter(Workspace.id == workspace_id)
            )
        ).scalars().first()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
            )

        ctx = AuthenticatedContext(session, workspace)
        try:
            ref = await generate(gen, ctx, payload)
        except gen.user_facing_errors as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except QuotaInsufficientError as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Out of credits for {gen.kind} generation.",
            ) from exc

        return gen.rest_response(ref)

    router.add_api_route(
        f"/workspaces/{{workspace_id}}/artifacts/{gen.kind}",
        endpoint,
        methods=["POST"],
        response_model=gen.output_schema,
        name=f"artifacts:generate_{gen.kind}",
        dependencies=[Depends(enforce_capability_rate_limit)],
    )
