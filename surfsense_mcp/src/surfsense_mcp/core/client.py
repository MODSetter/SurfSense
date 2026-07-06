"""Authenticated transport to a SurfSense backend's REST API.

Sends requests to fully-formed paths, returns parsed JSON, and turns any
transport or HTTP failure into a readable ``ToolError``.
"""

from __future__ import annotations

from typing import Any

import httpx

from .errors import ToolError

_FAILURE_HINTS: dict[int, str] = {
    401: "Authentication failed — check that SURFSENSE_PAT is a valid, unexpired token.",
    402: "The workspace is out of credits for this operation.",
    403: (
        "Access denied — the token lacks permission, or API access is disabled "
        "for this workspace (enable it in SurfSense workspace settings)."
    ),
    404: "The requested resource was not found.",
    429: "Rate limited by the backend — retry after a short pause.",
}


class SurfSenseClient:
    """Issues authenticated requests against ``{base_url}{api_prefix}``."""

    def __init__(self, *, api_base: str, pat: str, timeout: float) -> None:
        self._api_base = api_base
        self._http = httpx.AsyncClient(
            base_url=api_base,
            headers={
                "Authorization": f"Bearer {pat}",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: dict[str, Any] | None = None,
        files: Any | None = None,
    ) -> Any:
        """Send a request and return the parsed body, or raise ``ToolError``."""
        # Omit unset query params: sending them empty makes the API parse ""
        # as a value (e.g. int("") on folder_id) and fail.
        if params is not None:
            params = {key: value for key, value in params.items() if value is not None}
        try:
            response = await self._http.request(
                method, path, params=params, json=json, data=data, files=files
            )
        except httpx.RequestError as exc:
            raise ToolError(
                f"Could not reach SurfSense at {self._api_base}: {exc}. "
                "Confirm the backend is running and SURFSENSE_BASE_URL is correct."
            ) from exc

        if response.is_success:
            return self._parse_body(response)
        raise ToolError(self._explain_failure(response))

    async def aclose(self) -> None:
        await self._http.aclose()

    @staticmethod
    def _parse_body(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    @classmethod
    def _explain_failure(cls, response: httpx.Response) -> str:
        """Turn an error response into one actionable sentence for the model."""
        detail = cls._extract_detail(response)
        hint = _FAILURE_HINTS.get(response.status_code)
        if detail and hint:
            return f"{hint} (server said: {detail})"
        if detail:
            return f"SurfSense returned {response.status_code}: {detail}"
        return hint or f"SurfSense returned HTTP {response.status_code}."

    @staticmethod
    def _extract_detail(response: httpx.Response) -> str | None:
        try:
            body = response.json()
        except ValueError:
            return response.text.strip() or None
        if isinstance(body, dict):
            detail = body.get("detail", body)
            if isinstance(detail, dict):
                return detail.get("message") or str(detail)
            return str(detail)
        return str(body)
