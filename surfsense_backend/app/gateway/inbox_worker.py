"""FastAPI lifespan worker for gateway inbox processing."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.gateway.inbox_processor import claim_next_inbound_event, process_inbound_event

logger = logging.getLogger(__name__)

_task: asyncio.Task[None] | None = None


async def _process_inbox_forever() -> None:
    logger.info("Gateway inbox processor started in FastAPI process")
    while True:
        try:
            inbox_id = await claim_next_inbound_event()
            if inbox_id is None:
                await asyncio.sleep(0.5)
                continue
            logger.info("Gateway processing inbox_id=%s", inbox_id)
            await process_inbound_event(inbox_id)
            logger.info("Gateway processed inbox_id=%s", inbox_id)
        except asyncio.CancelledError:
            raise
        except RuntimeError as exc:
            if str(exc) == "gateway_thread_busy":
                logger.info("Gateway inbox_id busy; will retry from RECEIVED state")
            else:
                logger.exception("Gateway inbox processor failed one iteration")
            await asyncio.sleep(1)
        except Exception:
            logger.exception("Gateway inbox processor failed one iteration")
            await asyncio.sleep(1)


async def start_gateway_inbox_worker() -> None:
    global _task
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_process_inbox_forever(), name="gateway-inbox-worker")


async def stop_gateway_inbox_worker() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    with suppress(TimeoutError, asyncio.CancelledError):
        await asyncio.wait_for(_task, timeout=10)
    _task = None

