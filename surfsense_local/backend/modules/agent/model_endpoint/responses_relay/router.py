from dataclasses import replace
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from api.dependencies import SessionDep, transact
from modules.agent.launch_key import require_launch_key
from modules.agent.model_endpoint.error_replies import error_reply
from modules.agent.model_endpoint.model_address import (
    WrongRouteError,
    address_selected_model,
)
from modules.agent.model_endpoint.relay import RESPONSES, relay
from modules.agent.model_endpoint.responses_relay.plan_refusal import plan_refusal
from modules.agent.model_endpoint.responses_relay.plan_request import within_plan
from modules.egress.service import EgressDeniedError
from modules.llm.activity import ModelBusyError, model_activity
from modules.llm.providers.openai_responses import SignInRequiredError
from modules.llm.resolution import ModelResolutionError
from modules.llm.subscriptions.chatgpt.tokens import ConnectionAccess

router = APIRouter(
    prefix="/agent/model",
    tags=["agent"],
    dependencies=[Depends(require_launch_key)],
)


@router.post(
    "/v1/responses", summary="Answer opencode with a model that answers on /responses"
)
async def respond(
    payload: Annotated[dict[str, Any], Body()], session: SessionDep
) -> Response:
    """opencode's provider for a /responses model: an API key's, or a ChatGPT plan's.

    A plan's token is added here and refreshed once when refused, so the plan
    has one refresher, and each step is kept within what the plan takes.
    """
    try:
        address = await transact(session, address_selected_model, "responses")
    except WrongRouteError as failure:
        return error_reply(409, str(failure), "wrong_route")
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

    async def done() -> None:
        await model_activity.release_use(address.activity_key)

    body = {**payload, "model": address.name}
    if address.plan_connection_id is None:
        return await relay(address, body, done, wire=RESPONSES)

    access = ConnectionAccess(session.get_bind(), address.plan_connection_id)
    try:
        address = replace(address, headers=_bearer(await access(False)))
    except SignInRequiredError as failure:
        await done()
        return _sign_in_reply(failure)

    async def reauthorize() -> dict[str, str]:
        return _bearer(await access(True))

    try:
        return await relay(
            address,
            within_plan(body),
            done,
            wire=RESPONSES,
            reauthorize=reauthorize,
            refusal=plan_refusal,
        )
    except SignInRequiredError as failure:
        # The relay has released the model already.
        return _sign_in_reply(failure)


def _sign_in_reply(failure: SignInRequiredError) -> Response:
    return error_reply(401, str(failure), "subscription_sign_in")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
