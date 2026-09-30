from typing import Annotated

from fastapi import Depends, Request

from modules.events.broker import EventBroker


def get_event_broker(request: Request) -> EventBroker:
    """The app's one broker: every stream reads from it, every notice goes to it."""
    return request.app.state.broker


EventBrokerDep = Annotated[EventBroker, Depends(get_event_broker)]
