"""The approvals a Claude Code turn waits on, answered from the thread's approval card."""

import asyncio
import uuid
from typing import Literal

Reply = Literal["once", "reject"]


class Approvals:
    def __init__(self) -> None:
        self._waiting: dict[int, dict[str, asyncio.Future[Reply]]] = {}

    def ask(self, thread_id: int) -> tuple[str, asyncio.Future[Reply]]:
        """A new request, and the answer it will get."""
        request_id = f"perm_{uuid.uuid4().hex}"
        answer: asyncio.Future[Reply] = asyncio.get_running_loop().create_future()
        self._waiting.setdefault(thread_id, {})[request_id] = answer
        answer.add_done_callback(lambda _: self._forget(thread_id, request_id))
        return request_id, answer

    def answer(self, thread_id: int, request_id: str, reply: Reply) -> bool:
        """False when no such request waits, as for one already answered."""
        answer = self._waiting.get(thread_id, {}).get(request_id)
        if answer is None or answer.done():
            return False
        answer.set_result(reply)
        return True

    def drop(self, thread_id: int) -> None:
        """Refuse every request still waiting, as Stop does."""
        for answer in list(self._waiting.get(thread_id, {}).values()):
            if not answer.done():
                answer.set_result("reject")

    def _forget(self, thread_id: int, request_id: str) -> None:
        waiting = self._waiting.get(thread_id, {})
        waiting.pop(request_id, None)
        if not waiting:
            self._waiting.pop(thread_id, None)


# The API's one set, read by the turns and by the permission route.
APPROVALS = Approvals()
