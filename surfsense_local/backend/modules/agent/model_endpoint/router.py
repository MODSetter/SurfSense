from contextlib import AsyncExitStack
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from api.dependencies import SessionDep, transact
from modules.agent.launch_key import require_launch_key
from modules.agent.model_endpoint.admission_messages import admission_messages
from modules.agent.model_endpoint.error_replies import error_reply
from modules.agent.model_endpoint.model_address import address_selected_model
from modules.agent.model_endpoint.relay import relay
from modules.agent.model_endpoint.request_shaping import shaped_messages
from modules.egress.service import EgressDeniedError
from modules.llm.activity import ModelBusyError, model_activity
from modules.llm.admission.pool import LineFullError, Priority
from modules.llm.resolution import ModelResolutionError

router = APIRouter(
    prefix="/agent/model",
    tags=["agent"],
    dependencies=[Depends(require_launch_key)],
)


@router.post("/v1/chat/completions", summary="Answer opencode with the selected model")
async def complete_chat(
    payload: Annotated[dict[str, Any], Body()], session: SessionDep, request: Request
) -> Response:
    """The one route opencode's provider calls, for every model local or remote.

    The selected model is resolved on each request, so a change of model in the
    app applies from opencode's next turn.
    """
    try:
        address = await transact(session, address_selected_model)
    except ModelResolutionError as failure:
        return error_reply(409, str(failure), "model_not_selected")
    except EgressDeniedError as refused:
        return error_reply(403, str(refused), "egress_disabled")
    except HTTPException as failure:
        return error_reply(failure.status_code, str(failure.detail))

    try:
        await model_activity.acquire_use(address.activity_key)
    except ModelBusyError as busy:
        return error_reply(409, str(busy), "model_busy")

    body = {
        **payload,
        "model": address.name,
        "messages": shaped_messages(payload.get("messages") or []),
    }
    # Each step is admitted on its own and released when its reply ends, so a
    # growing tool loop is priced afresh every step and holds no room while
    # opencode runs a tool.
    held = AsyncExitStack()
    try:
        if address.local_runtime:
            await held.enter_async_context(
                request.app.state.local_admission.admitted(
                    address.name,
                    admission_messages(body["messages"]),
                    _max_tokens(payload),
                    Priority.INTERACTIVE,
                )
            )
    except BaseException as failure:
        await model_activity.release_use(address.activity_key)
        if isinstance(failure, LineFullError):
            return error_reply(429, str(failure), "too_many_requests")
        raise

    async def done() -> None:
        await held.aclose()
        await model_activity.release_use(address.activity_key)

    return await relay(address, body, done)


def _max_tokens(payload: dict[str, Any]) -> int | None:
    """The answer's cap as the request states it, under either spelling."""
    for field in ("max_completion_tokens", "max_tokens"):
        value = payload.get(field)
        if isinstance(value, int) and value > 0:
            return value
    return None
