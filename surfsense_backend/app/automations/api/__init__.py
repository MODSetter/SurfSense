"""HTTP layer for the automations feature."""

from __future__ import annotations

from fastapi import APIRouter

from .automation import router as automation_router
from .run import router as run_router
from .trigger import router as trigger_router

router = APIRouter()
router.include_router(automation_router)
router.include_router(trigger_router)
router.include_router(run_router)

__all__ = ["router"]
