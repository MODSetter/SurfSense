"""Generate the agent door from the capability registry (05).

One LangChain tool per verb; each runs the same thin adapter as the REST door
(``access/rest.py``): meter-gate -> executor -> charge. The tool returns the
verb's serialized output so the model can reason over it; UI cards are the SSE
emission handler's job, not this generator's.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool, StructuredTool

from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.store import all_capabilities
from app.capabilities.core.types import Capability, CapabilityContext
from app.db import async_session_maker
from app.services.web_crawl_credit_service import InsufficientCreditsError


def build_capability_tools(
    *,
    workspace_id: int,
    capabilities: list[Capability] | None = None,
) -> list[BaseTool]:
    """Emit one tool per verb (defaults to the whole registry)."""
    caps = capabilities if capabilities is not None else all_capabilities()
    return [_capability_tool(cap, workspace_id) for cap in caps]


def _capability_tool(capability: Capability, workspace_id: int) -> BaseTool:
    input_model = capability.input_schema
    unit = capability.billing_unit
    executor = capability.executor

    async def _run(**kwargs: object) -> dict | str:
        payload = input_model(**kwargs)
        async with async_session_maker() as session:
            ctx = CapabilityContext(session=session, workspace_id=workspace_id)
            try:
                await gate_capability(payload, unit, ctx)
            except InsufficientCreditsError as exc:
                return str(exc)
            output = await executor(payload)
            await charge_capability(output, unit, ctx)
            return output.model_dump()

    return StructuredTool.from_function(
        coroutine=_run,
        name=capability.name.replace(".", "_"),
        description=capability.description,
        args_schema=input_model,
    )
