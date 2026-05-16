"""SurfSense arm: per-question fresh thread + ``/api/v1/new_chat`` stream.

For every question:

* Create a fresh ``NewChatThread`` on the suite's pinned SearchSpace.
  This sidesteps the per-thread ``THREAD_BUSY`` 409 (a single thread
  serialises turns, see ``surfsense_backend/app/routes/new_chat_routes.py:191-220``).
* POST ``/api/v1/new_chat`` with the prompt and the per-question
  ``mentioned_document_ids`` (``surfsense_backend/app/schemas/new_chat.py:241-243``).
* Consume the SSE stream via ``NewChatClient.ask`` which accumulates
  text deltas and returns ``StreamedAnswer``.
* Optionally delete the thread (default ON for ephemeral runs).

Citations are parsed from the streamed assistant text via the
canonical regex port; chunk ids are returned in ``ArmResult.citations``
for the runner to map back to corpus ids.
"""

from __future__ import annotations

import logging

from ..clients import NewChatClient
from ..parse.answer_letter import extract_answer_letter
from .base import Arm, ArmRequest, ArmResult

logger = logging.getLogger(__name__)


class SurfSenseArm(Arm):
    """``Arm`` implementation backed by ``NewChatClient``."""

    name: str = "surfsense"

    def __init__(
        self,
        *,
        client: NewChatClient,
        search_space_id: int,
        ephemeral_threads: bool = True,
        thread_title_prefix: str = "eval",
    ) -> None:
        self._client = client
        self._search_space_id = search_space_id
        self._ephemeral = ephemeral_threads
        self._title_prefix = thread_title_prefix

    async def answer(self, request: ArmRequest) -> ArmResult:
        thread_id: int | None = None
        try:
            thread_id = await self._client.create_thread(
                search_space_id=self._search_space_id,
                title=f"{self._title_prefix}:{request.question_id}",
            )
            answer = await self._client.ask(
                thread_id=thread_id,
                search_space_id=self._search_space_id,
                user_query=request.prompt,
                mentioned_document_ids=request.mentioned_document_ids,
                disabled_tools=request.options.get("disabled_tools"),
            )
        except Exception as exc:  # noqa: BLE001
            return ArmResult(
                arm=self.name,
                question_id=request.question_id,
                raw_text="",
                error=f"{type(exc).__name__}: {exc}",
                extra={"thread_id": thread_id},
            )
        finally:
            if self._ephemeral and thread_id is not None:
                try:
                    await self._client.delete_thread(thread_id)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "Failed to delete thread %s: %s", thread_id, exc
                    )

        letter = extract_answer_letter(answer.text)
        return ArmResult(
            arm=self.name,
            question_id=request.question_id,
            raw_text=answer.text,
            answer_letter=letter.letter,
            citations=answer.citations,
            latency_ms=answer.latency_ms,
            # SurfSense doesn't surface input/output token counts in the
            # SSE stream today; leaving the cost / token fields at 0
            # documents that gap. Estimating from the raw text would
            # bias the comparison against the SurfSense arm.
            extra={
                "thread_id": thread_id,
                "search_space_id": self._search_space_id,
                "answer_letter_strategy": letter.strategy,
                "user_message_id": answer.user_message_id,
                "assistant_message_id": answer.assistant_message_id,
                "finished_normally": answer.finished_normally,
                "n_raw_events": len(answer.raw_events),
                "n_mentioned_documents": len(request.mentioned_document_ids or []),
            },
        )


__all__ = ["SurfSenseArm"]
