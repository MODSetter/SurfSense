"""HTTP layer for the automations feature."""

from __future__ import annotations

from fastapi import APIRouter

from .automation import router as automation_router

router = APIRouter()
router.include_router(automation_router)

__all__ = ["router"]
