"""Repair dangling tool-call sequences before each agent turn."""

from __future__ import annotations

from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware


def build_patch_tool_calls_mw() -> PatchToolCallsMiddleware:
    return PatchToolCallsMiddleware()
