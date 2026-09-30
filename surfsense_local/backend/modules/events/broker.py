import asyncio

from modules.events.schemas import InternalEvent


class EventBroker:
    """In-process pub/sub fanning change notices out to open SSE streams.

    One uvicorn worker serves the local app, so a plain in-memory map suffices.
    ponytail: single process; ceiling is multi-process, upgrade is Redis pub/sub.
    """

    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue[dict]]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def subscribe(self, workspace_id: int) -> asyncio.Queue[dict]:
        # Streams subscribe from the server's loop: the one its queues are fed on.
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self._subscribers.setdefault(workspace_id, set()).add(queue)
        return queue

    def unsubscribe(self, workspace_id: int, queue: asyncio.Queue[dict]) -> None:
        subscribers = self._subscribers.get(workspace_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            del self._subscribers[workspace_id]

    def publish(self, notice: InternalEvent) -> None:
        # A missed subscriber is fine: the client's polling fallback catches up.
        # Handed to the loop, not put directly: a `def` route publishes from a
        # threadpool thread, and asyncio queues are not thread-safe.
        event = {"kind": notice.kind, "ids": notice.ids, "status": notice.status}
        for queue in tuple(self._subscribers.get(notice.workspace_id, ())):
            self._loop.call_soon_threadsafe(queue.put_nowait, event)
