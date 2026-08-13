"""Request-scoped context that decides *how* a generation runs.

The generic ``generate()`` pipeline is written once; the context supplies the
three steps that differ between callers: which model to resolve, how to meter,
and how to deliver the output. Authenticated callers bill a workspace wallet
and persist an Artifact; anonymous callers skip both and get raw bytes.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Protocol

from app.services.billable_calls import billable_call

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic import BaseModel
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.artifacts.generation.core.registry import ArtifactGenerator
    from app.artifacts.generation.core.result import GenerationResult
    from app.db import Workspace


class GenerationContext(Protocol):
    async def resolve(self, gen: ArtifactGenerator, req: BaseModel) -> Any: ...

    def meter(self, gen: ArtifactGenerator, model: Any, req: BaseModel): ...

    async def deliver(
        self, gen: ArtifactGenerator, req: BaseModel, model: Any, response: dict
    ) -> GenerationResult: ...


async def generate(
    gen: ArtifactGenerator, ctx: GenerationContext, req: BaseModel
) -> GenerationResult:
    """Resolve the model, meter the call, run the provider, deliver the result."""
    model = await ctx.resolve(gen, req)
    async with ctx.meter(gen, model, req):
        response = await gen.run(model, req)
    return await ctx.deliver(gen, req, model, response)


class AuthenticatedContext:
    """Workspace caller: bill the wallet, persist a real Artifact."""

    def __init__(
        self,
        session: AsyncSession,
        workspace: Workspace,
        *,
        image_gen_model_id_override: int | None = None,
        thread_id: int | None = None,
        tool_call_id: str | None = None,
        committed_by_turn: bool = False,
    ) -> None:
        self.session = session
        self.workspace = workspace
        self.override = image_gen_model_id_override
        self.thread_id = thread_id
        self.tool_call_id = tool_call_id
        self.committed_by_turn = committed_by_turn

    async def resolve(self, gen: ArtifactGenerator, req: BaseModel) -> Any:
        return await gen.resolve_workspace(self.session, self.workspace, self.override)

    @asynccontextmanager
    async def meter(
        self, gen: ArtifactGenerator, model: Any, req: BaseModel
    ) -> AsyncIterator[None]:
        tier, base_model, reserve = await gen.billing(
            self.session, model, self.workspace
        )
        async with billable_call(
            user_id=self.workspace.user_id,
            workspace_id=self.workspace.id,
            billing_tier=tier,
            base_model=base_model,
            quota_reserve_micros_override=reserve,
            usage_type=gen.usage_type,
            call_details={"model": base_model, **gen.audit(req)},
        ):
            yield

    async def deliver(
        self, gen: ArtifactGenerator, req: BaseModel, model: Any, response: dict
    ) -> GenerationResult:
        ref = await gen.persist(
            self.session,
            workspace_id=self.workspace.id,
            req=req,
            model=model,
            response=response,
            thread_id=self.thread_id,
            tool_call_id=self.tool_call_id,
            committed_by_turn=self.committed_by_turn,
        )
        await self.session.commit()
        return ref


class AnonymousContext:
    """Public funnel caller: no wallet (the door enforces an IP cap), no persist."""

    async def resolve(self, gen: ArtifactGenerator, req: BaseModel) -> Any:
        return gen.resolve_anonymous()

    @asynccontextmanager
    async def meter(
        self, gen: ArtifactGenerator, model: Any, req: BaseModel
    ) -> AsyncIterator[None]:
        yield

    async def deliver(
        self, gen: ArtifactGenerator, req: BaseModel, model: Any, response: dict
    ) -> GenerationResult:
        return await gen.to_bytes(response)
