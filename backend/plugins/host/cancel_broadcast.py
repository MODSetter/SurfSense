"""A Stop sent to any copy of the host, passed to every copy, since any may run the call."""

import json
import logging
from collections.abc import Callable
from typing import Protocol

import anyio
import redis.asyncio as redis
from anyio.abc import TaskStatus

logger = logging.getLogger(__name__)

OnCancel = Callable[[str, str], None]
CHANNEL = "surfsense:plugin-calls:cancel"
# How soon a copy tries Redis again after losing it.
RETRY_SECONDS = 1.0
CONNECT_TIMEOUT_SECONDS = 2.0


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
    """Every copy, through a Redis channel every copy listens on.

    Redis runs as a container that restarts with the platform, so a copy starts
    without it, resubscribes when it returns, and while it is down a Stop still
    ends the calls on the copy that took it.
    """

    def __init__(self, url: str, retry_seconds: float = RETRY_SECONDS) -> None:
        self._url = url
        self._retry_seconds = retry_seconds
        self._listeners: list[OnCancel] = []

    async def publish(self, who: str, token: str) -> None:
        try:
            async with _client(self._url) as client:
                await client.publish(CHANNEL, json.dumps([who, token]))
        except redis.RedisError as error:
            logger.warning(
                "Redis unreachable, so the Stop ends this copy's calls only: %s", error
            )
            for on_cancel in self._listeners:
                on_cancel(who, token)

    async def listen(
        self,
        on_cancel: OnCancel,
        *,
        task_status: TaskStatus[None] = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        self._listeners.append(on_cancel)
        # Reported once subscribed, so a Stop right after startup is heard; or
        # once the first try fails, so a copy serves while Redis is down.
        started = False
        try:
            while True:
                try:
                    async with _client(self._url) as client, client.pubsub() as channel:
                        await channel.subscribe(CHANNEL)
                        if not started:
                            task_status.started()
                            started = True
                        async for message in channel.listen():
                            if message["type"] == "message":
                                on_cancel(*json.loads(message["data"]))
                except redis.RedisError as error:
                    logger.warning("Redis unreachable, retrying: %s", error)
                if not started:
                    task_status.started()
                    started = True
                await anyio.sleep(self._retry_seconds)
        finally:
            self._listeners.remove(on_cancel)


def _client(url: str) -> redis.Redis:
    # A short connect timeout, so a Stop never waits long on a Redis that is down.
    return redis.from_url(url, socket_connect_timeout=CONNECT_TIMEOUT_SECONDS)
