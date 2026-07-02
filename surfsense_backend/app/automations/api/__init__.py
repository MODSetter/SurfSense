"""HTTP layer for the automations feature."""

from __future__ import annotations

from fastapi import APIRouter

from .automation import router as automation_router
from .chat_watch import router as watch_router
from .run import router as run_router
from .trigger import router as trigger_router

router = APIRouter()
# Before automation_router so the literal ``/automations/watches`` path is not
# shadowed by the ``/automations/{automation_id}`` route.
router.include_router(watch_router)
router.include_router(automation_router)
router.include_router(trigger_router)
router.include_router(run_router)

__all__ = ["router"]
