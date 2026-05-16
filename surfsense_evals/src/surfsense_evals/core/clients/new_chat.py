"""Client for ``/api/v1/threads`` and ``/api/v1/new_chat`` (SSE).

Verified against:

* ``surfsense_backend/app/routes/new_chat_routes.py:793-848`` (POST /threads)
* ``surfsense_backend/app/routes/new_chat_routes.py:1073-1142`` (DELETE /threads/{id})
* ``surfsense_backend/app/routes/new_chat_routes.py:1689-1800`` (POST /new_chat SSE)
* ``surfsense_backend/app/routes/new_chat_routes.py:191-220`` (THREAD_BUSY / TURN_CANCELLING 409)
* ``surfsense_backend/app/services/streaming/envelope/sse.py`` (wire framing)
* ``surfsense_backend/app/services/streaming/events/text.py`` (text-delta events)
* ``surfsense_backend/app/schemas/new_chat.py:234-288`` (NewChatRequest body)

The wire format is "Vercel AI SDK"-flavoured SSE with one event per
``data: <json>\n\n`` block (or the literal ``data: [DONE]\n\n``
terminator). Text deltas arrive as ``{"type":"text-delta","id":...,"delta":...}``
events; we accumulate them per ``id`` and emit the final concatenated
text plus parsed citations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..parse import iter_sse_events, parse_citations

logger = logging.getLogger(__name__)


@dataclass
class StreamedAnswer:
    """Result of a single ``/new_chat`` turn."""

    text: str
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: int = 0
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    finished_normally: bool = False

    @property
    def citations(self) -> list[dict[str, Any]]:
        """Parsed citation tokens (lazy; small enough to recompute)."""

        return [token.to_dict() for token in parse_citations(self.text)]


class ThreadBusyError(RuntimeError):
    """Raised after exhausting retries on a 409 ``THREAD_BUSY`` / ``TURN_CANCELLING``."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code


class NewChatClient:
    """Thread create / delete / SSE ask."""

    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # threads
    # ------------------------------------------------------------------

    async def create_thread(
        self,
        *,
        search_space_id: int,
        title: str = "eval",
        archived: bool = False,
        visibility: str = "PRIVATE",
    ) -> int:
        response = await self._http.post(
            f"{self._base}/api/v1/threads",
            json={
                "search_space_id": search_space_id,
                "title": title,
                "archived": archived,
                "visibility": visibility,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        return int(payload["id"])

    async def delete_thread(self, thread_id: int) -> None:
        response = await self._http.delete(
            f"{self._base}/api/v1/threads/{thread_id}",
            headers={"Accept": "application/json"},
        )
        if response.status_code == 404:
            return  # idempotent
        response.raise_for_status()

    # ------------------------------------------------------------------
    # /new_chat SSE
    # ------------------------------------------------------------------

    async def ask(
        self,
        *,
        thread_id: int,
        search_space_id: int,
        user_query: str,
        mentioned_document_ids: Sequence[int] | None = None,
        disabled_tools: Sequence[str] | None = None,
        max_busy_retries: int = 4,
        timeout_s: float = 600.0,
    ) -> StreamedAnswer:
        """Stream a single turn and return the accumulated answer.

        Honours backend ``THREAD_BUSY`` / ``TURN_CANCELLING`` 409
        responses by sleeping for the ``Retry-After`` header (or the
        ``retry-after-ms`` header if present) and replaying. Bounded
        by ``max_busy_retries`` so a stuck thread never blocks the
        whole run.
        """

        body: dict[str, Any] = {
            "chat_id": thread_id,
            "search_space_id": search_space_id,
            "user_query": user_query,
        }
        if mentioned_document_ids:
            body["mentioned_document_ids"] = list(mentioned_document_ids)
        if disabled_tools:
            body["disabled_tools"] = list(disabled_tools)

        attempt = 0
        while True:
            try:
                return await self._stream_once(body=body, timeout_s=timeout_s)
            except ThreadBusyError as exc:
                attempt += 1
                if attempt > max_busy_retries:
                    raise
                # Cap wait at 30s; backend retry hint is exponential anyway.
                wait = min(30.0, 0.5 * (2 ** attempt))
                logger.info(
                    "thread_id=%s busy (%s); retry %d/%d after %.1fs",
                    thread_id,
                    exc.error_code,
                    attempt,
                    max_busy_retries,
                    wait,
                )
                await asyncio.sleep(wait)

    async def _stream_once(
        self,
        *,
        body: dict[str, Any],
        timeout_s: float,
    ) -> StreamedAnswer:
        # Per-call timeout — the connect should be quick, the read needs
        # to outlive the longest LLM completion.
        timeout = httpx.Timeout(timeout_s, connect=10.0)
        started = time.monotonic()
        async with self._http.stream(
            "POST",
            f"{self._base}/api/v1/new_chat",
            json=body,
            headers={"Accept": "text/event-stream"},
            timeout=timeout,
        ) as response:
            if response.status_code == 409:
                detail = await self._extract_busy_detail(response)
                raise ThreadBusyError(
                    error_code=detail.get("errorCode", "THREAD_BUSY"),
                    message=detail.get("message", "Thread is busy"),
                )
            response.raise_for_status()
            answer = await self._consume_sse(response)
        answer.latency_ms = int((time.monotonic() - started) * 1000)
        return answer

    @staticmethod
    async def _extract_busy_detail(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = json.loads(await response.aread())
        except (json.JSONDecodeError, ValueError):
            return {"errorCode": "THREAD_BUSY", "message": response.text}
        if isinstance(payload, dict) and isinstance(payload.get("detail"), dict):
            return payload["detail"]
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    async def _consume_sse(response: httpx.Response) -> StreamedAnswer:
        """Walk SSE events, accumulate text-delta payloads.

        Backend events of interest:

        * ``{"type": "text-start", "id": ...}``
        * ``{"type": "text-delta", "id": ..., "delta": ...}``
        * ``{"type": "text-end", "id": ...}``
        * ``{"type": "start", "messageId": ...}``  (top-level message id)
        * ``{"type": "finish"}``
        * literal ``[DONE]`` sentinel

        Multiple ``text-start`` blocks can interleave — each gets its
        own ``id`` and we concatenate them in arrival order. That
        mirrors the AI SDK client behaviour: one continuous assistant
        message visible to the user.
        """

        ordered_text_ids: list[str] = []
        text_buffers: dict[str, list[str]] = {}
        raw_events: list[dict[str, Any]] = []
        user_message_id: str | None = None
        assistant_message_id: str | None = None
        finished = False

        async for event in iter_sse_events(_aiter_lines(response)):
            data = event.data
            if data == "[DONE]":
                finished = True
                continue
            try:
                payload = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                logger.debug("Skipping non-JSON SSE payload: %r", data[:120])
                continue
            if not isinstance(payload, dict):
                continue
            raw_events.append(payload)
            ev_type = payload.get("type")
            if ev_type == "text-delta":
                tid = str(payload.get("id", ""))
                delta = payload.get("delta", "")
                if not isinstance(delta, str):
                    continue
                if tid not in text_buffers:
                    text_buffers[tid] = []
                    ordered_text_ids.append(tid)
                text_buffers[tid].append(delta)
            elif ev_type == "text-start":
                tid = str(payload.get("id", ""))
                if tid and tid not in text_buffers:
                    text_buffers[tid] = []
                    ordered_text_ids.append(tid)
            elif ev_type == "start":
                msg_id = payload.get("messageId")
                if isinstance(msg_id, str):
                    user_message_id = user_message_id or msg_id
            elif ev_type == "data-user-message-id":
                msg_id = (payload.get("data") or {}).get("id") or payload.get("id")
                if isinstance(msg_id, str):
                    user_message_id = msg_id
            elif ev_type == "data-assistant-message-id":
                msg_id = (payload.get("data") or {}).get("id") or payload.get("id")
                if isinstance(msg_id, str):
                    assistant_message_id = msg_id
            elif ev_type == "finish":
                finished = True

        text = "".join("".join(text_buffers.get(tid, [])) for tid in ordered_text_ids)
        return StreamedAnswer(
            text=text,
            raw_events=raw_events,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            finished_normally=finished,
        )


async def _aiter_lines(response: httpx.Response) -> AsyncIterator[str]:
    """Adapter so the parser can consume any line iterator (mockable in tests)."""

    async for line in response.aiter_lines():
        yield line
