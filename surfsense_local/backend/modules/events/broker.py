import asyncio


class EventBroker:
    """In-process pub/sub fanning worker notifications out to open SSE streams.

    One uvicorn worker serves the local app, so a plain in-memory map suffices.
    ponytail: single process; ceiling is multi-process, upgrade is Redis pub/sub.
    """

    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue[dict]]] = {}

    def subscribe(self, workspace_id: int) -> asyncio.Queue[dict]:
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

    def publish(self, workspace_id: int, event: dict) -> None:
        # A missed subscriber is fine: the client's polling fallback catches up.
        for queue in self._subscribers.get(workspace_id, ()):
            queue.put_nowait(event)
