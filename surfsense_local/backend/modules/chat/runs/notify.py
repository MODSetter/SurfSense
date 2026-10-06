from modules.events.broker import EventBroker
from modules.events.schemas import EventKind, InternalEvent


def notify_run(
    broker: EventBroker, workspace_id: int, thread_id: int, status: str
) -> None:
    """Tell every open window a thread started (`running`) or stopped (`done`)
    answering, so its Chats dialog and button follow without polling."""
    broker.publish(
        InternalEvent(
            workspace_id=workspace_id,
            kind=EventKind.CHAT_RUNS,
            ids=[thread_id],
            status=status,
        )
    )
