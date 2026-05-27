"""Service layer for the automations feature."""

from __future__ import annotations

from .automation import AutomationService, get_automation_service

__all__ = ["AutomationService", "get_automation_service"]
