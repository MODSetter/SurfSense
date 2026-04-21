"""Standardised response dict factories for LangChain agent tools."""

from __future__ import annotations

from typing import Any


class ToolResponse:

    @staticmethod
    def success(message: str, **data: Any) -> dict[str, Any]:
        return {"status": "success", "message": message, **data}

    @staticmethod
    def error(error: str, **data: Any) -> dict[str, Any]:
        return {"status": "error", "error": error, **data}

    @staticmethod
    def auth_error(service: str, **data: Any) -> dict[str, Any]:
        return {
            "status": "auth_error",
            "error": (
                f"{service} authentication has expired or been revoked. "
                "Please re-connect the integration in Settings → Connectors."
            ),
            **data,
        }

    @staticmethod
    def rejected(message: str = "Action was declined by the user.") -> dict[str, Any]:
        return {"status": "rejected", "message": message}

    @staticmethod
    def not_found(
        resource: str, identifier: str, **data: Any
    ) -> dict[str, Any]:
        return {
            "status": "not_found",
            "error": f"{resource} '{identifier}' was not found.",
            **data,
        }
