from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.egress import service as egress
from modules.egress.models import EgressDestination
from modules.llm.connections.serves import served_by
from modules.llm.subscriptions.chatgpt import account
from modules.llm.subscriptions.chatgpt.endpoints import get_endpoints
from modules.llm.subscriptions.chatgpt.flows import SignInFlows
from modules.llm.subscriptions.chatgpt.schemas import (
    SignInHost,
    SignInOption,
    SignInRead,
    SignInStarted,
    SignInWrite,
)

router = APIRouter(prefix="/connections")


def get_flows(request: Request) -> SignInFlows:
    flows = getattr(request.app.state, "chatgpt_sign_in", None)
    if flows is None:
        flows = request.app.state.chatgpt_sign_in = SignInFlows()
    return flows


FlowsDep = Annotated[SignInFlows, Depends(get_flows)]


def _ready_to_sign_in(session: Session, payload: SignInWrite) -> None:
    """Refuse what the sign-in could not finish, before a browser opens for it."""
    endpoints = get_endpoints()
    for url in (endpoints.auth_url, endpoints.api_url):
        egress.require(session, egress.host_destination(url))
    try:
        if payload.connection_id is not None:
            account.chatgpt_connection(session, payload.connection_id)
        else:
            account.require_free_label(session, payload.label.strip())
    except account.NotChatGPTError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except account.LabelTakenError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error


@router.get("/chatgpt")
def sign_in_option(session: SessionDep) -> SignInOption:
    """What a ChatGPT connection would serve, and the hosts still off, asked
    about one by one before the sign-in starts.

    `request` asks about one refused host per call, and cannot tell a host
    the user declined from a second one, so the renderer asks from this list.
    """
    endpoints = get_endpoints()
    refused: list[SignInHost] = []
    for url in (endpoints.auth_url, endpoints.api_url):
        destination = egress.host_destination(url)
        row = session.get(EgressDestination, destination) if destination else None
        if destination and (row is None or not row.enabled):
            refused.append(
                SignInHost(destination=destination, host=egress.host_of(destination))
            )
    return SignInOption(serves=list(served_by(account.CHATGPT)), hosts=refused)


@router.post("/chatgpt/sign-in", status_code=status.HTTP_201_CREATED)
async def start_sign_in(
    payload: SignInWrite, request: Request, session: SessionDep, flows: FlowsDep
) -> SignInStarted:
    await transact(session, _ready_to_sign_in, payload)
    flow = await flows.start(
        request.app.state.session_factory,
        label=payload.label.strip() if payload.label else None,
        connection_id=payload.connection_id,
    )
    return SignInStarted(flow_id=flow.id, authorize_url=flow.authorize_url)


@router.get("/chatgpt/sign-in/{flow_id}")
def read_sign_in(flow_id: str, flows: FlowsDep) -> SignInRead:
    flow = flows.get(flow_id)
    if flow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such sign-in")
    return SignInRead(
        status=flow.status, connection_id=flow.connection_id, message=flow.message
    )


@router.delete("/chatgpt/sign-in/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_sign_in(flow_id: str, flows: FlowsDep) -> Response:
    flows.cancel(flow_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{connection_id}/sign-in", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(connection_id: int, session: SessionDep) -> Response:
    try:
        account.sign_out(session, connection_id)
    except account.NotChatGPTError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
