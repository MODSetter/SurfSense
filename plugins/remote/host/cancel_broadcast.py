"""A Stop sent to any copy of the host, passed to every copy, since any may run the call."""

import json
from collections.abc import Callable
from typing import Protocol

import anyio
import redis.asyncio as redis
from anyio.abc import TaskStatus

OnCancel = Callable[[str, str], None]
CHANNEL = "surfsense:plugin-calls:cancel"


class CancelBroadcast(Protocol):
    async def publish(self, who: str, token: str) -> None: ...

    async def listen(
        self, on_cancel: OnCancel, *, task_status: TaskStatus[None]
    ) -> None:
        """Runs until cancelled; reports started once it hears every publish."""
        ...


class LocalBroadcast:
    """One copy of the host: a Stop goes no further than this process."""

    def __init__(self) -> None:
        self._listeners: list[OnCancel] = []

    async def publish(self, who: str, token: str) -> None:
        for on_cancel in self._listeners:
            on_cancel(who, token)

    async def listen(
        self,
        on_cancel: OnCancel,
        *,
        task_status: TaskStatus[None] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        self._listeners.append(on_cancel)
        task_status.started()
        try:
            await anyio.sleep_forever()
        finally:
            self._listeners.remove(on_cancel)


class RedisBroadcast:
    """Every copy, through a Redis channel every copy listens on."""

    def __init__(self, url: str) -> None:
        self._url = url

    async def publish(self, who: str, token: str) -> None:
        async with redis.from_url(self._url) as client:
            await client.publish(CHANNEL, json.dumps([who, token]))

    async def listen(
        self,
        on_cancel: OnCancel,
        *,
        task_status: TaskStatus[None] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        async with redis.from_url(self._url) as client, client.pubsub() as channel:
            await channel.subscribe(CHANNEL)
            task_status.started()
            async for message in channel.listen():
                if message["type"] == "message":
                    on_cancel(*json.loads(message["data"]))
