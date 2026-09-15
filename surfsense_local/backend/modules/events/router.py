import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import StreamingResponse

from modules.events.broker import EventBroker
from modules.events.schemas import InternalEvent
from modules.workspaces.dependencies import WorkspaceDep

router = APIRouter(tags=["events"])

# Same headers as chat's stream: stop a proxy buffering a live stream into one blob.
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

# Idle gap after which a comment keeps the connection (and any proxy) alive.
_HEARTBEAT_SECONDS = 15


@router.get(
    "/workspaces/{workspace_id}/events",
    summary="Stream a workspace's change events",
)
async def subscribe_events(
    workspace: WorkspaceDep, request: Request
) -> StreamingResponse:
    broker: EventBroker = request.app.state.broker
    queue = broker.subscribe(workspace.id)

    async def stream() -> AsyncIterator[bytes]:
        # A first byte tells the client it is subscribed; publishes now reach it.
        yield b": connected\n\n"
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), _HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield b": ping\n\n"
                    continue
                yield _event(event)
        finally:
            broker.unsubscribe(workspace.id, queue)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers=_SSE_HEADERS
    )


@router.post(
    "/internal/events",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Worker-to-API change notice (loopback only)",
)
async def publish_event(payload: InternalEvent, request: Request) -> Response:
    # Loopback only by convention: uvicorn binds 127.0.0.1, so nothing off-box reaches this.
    broker: EventBroker = request.app.state.broker
    broker.publish(
        payload.workspace_id,
        {"kind": payload.kind, "ids": payload.ids, "status": payload.status},
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)


def _event(event: dict) -> bytes:
    """One named SSE event: an `event:` name the client listens for, then its JSON."""
    data = json.dumps({"ids": event["ids"], "status": event["status"]})
    return f"event: {event['kind']}\ndata: {data}\n\n".encode()
