"""Generate the REST door from the capability registry (05).

One typed ``POST`` per verb; each runs the same thin adapter:
authn -> workspace authz -> meter-gate -> executor -> charge -> typed output.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.capabilities.core.access.rate_limit import enforce_capability_rate_limit
from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.store import all_capabilities
from app.capabilities.core.types import Capability, CapabilityContext
from app.db import get_async_session
from app.exceptions import ExternalServiceError, SurfSenseError
from app.services.web_crawl_credit_service import InsufficientCreditsError
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access


def build_capabilities_router(
    capabilities: list[Capability] | None = None,
) -> APIRouter:
    """Emit one typed route per verb (defaults to the whole registry)."""
    router = APIRouter(tags=["capabilities"])
    caps = capabilities if capabilities is not None else all_capabilities()
    for capability in caps:
        _register_verb(router, capability)
    return router


def _register_verb(router: APIRouter, capability: Capability) -> None:
    input_model = capability.input_schema
    output_model = capability.output_schema
    unit = capability.billing_unit
    executor = capability.executor

    async def endpoint(
        workspace_id: int,
        payload: input_model,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        await check_workspace_access(session, auth, workspace_id)
        ctx = CapabilityContext(session=session, workspace_id=workspace_id)
        try:
            await gate_capability(payload, unit, ctx)
        except InsufficientCreditsError as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error_code": "insufficient_credits",
                    "message": str(exc),
                    "balance_micros": exc.balance_micros,
                    "required_micros": exc.required_micros,
                },
            ) from exc

        try:
            output = await executor(payload)
        except (SurfSenseError, HTTPException):
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"The '{capability.name}' capability failed due to an upstream error.",
                code="CAPABILITY_UPSTREAM_ERROR",
            ) from exc

        await charge_capability(output, unit, ctx)
        return output

    router.add_api_route(
        f"/workspaces/{{workspace_id}}/capabilities/{capability.name}",
        endpoint,
        methods=["POST"],
        response_model=output_model,
        name=f"capability:{capability.name}",
        dependencies=[Depends(enforce_capability_rate_limit)],
    )
