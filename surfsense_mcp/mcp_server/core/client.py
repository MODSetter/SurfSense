"""Authenticated transport to a SurfSense backend's REST API.

Sends requests to fully-formed paths, returns parsed JSON, and turns any
transport or HTTP failure into a readable ``ToolError``.
"""

from __future__ import annotations

from typing import Any

import httpx

from .auth.identity import current_api_key
from .errors import ToolError

_FAILURE_HINTS: dict[int, str] = {
    401: "Authentication failed — the SurfSense API key is invalid or expired.",
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

    def __init__(
        self, *, api_base: str, timeout: float, fallback_api_key: str | None = None
    ) -> None:
        self._api_base = api_base
        # Resolved per request, so no key is baked into the shared client. The
        # fallback is the env key used under stdio, where there is no header.
        self._fallback_api_key = fallback_api_key
        self._http = httpx.AsyncClient(
            base_url=api_base,
            # ``X-SurfSense-Client`` lets the backend distinguish PAT traffic
            # originating from this MCP server vs. raw PAT scripts, so
            # "documents added via MCP" / "searches via MCP" are queryable.
            # Server-to-server, so no CORS implications.
            headers={"Accept": "application/json", "X-SurfSense-Client": "mcp"},
            timeout=timeout,
        )

    def _auth_headers(self) -> dict[str, str]:
        """Resolve the caller's key: the per-request header, else the env key."""
        api_key = current_api_key() or self._fallback_api_key
        if not api_key:
            raise ToolError(
                "No SurfSense API key supplied. Send it as an 'Authorization: "
                "Bearer ss_pat_...' header (remote server), or set the "
                "SURFSENSE_API_KEY environment variable (stdio)."
            )
        return {"Authorization": f"Bearer {api_key}"}

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: dict[str, Any] | None = None,
        files: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Send a request and return the parsed body, or raise ``ToolError``.

        ``headers`` overrides the client defaults for this call.
        """
        # Omit unset query params: sending them empty makes the API parse ""
        # as a value (e.g. int("") on folder_id) and fail.
        if params is not None:
            params = {key: value for key, value in params.items() if value is not None}
        headers = {**self._auth_headers(), **(headers or {})}
        try:
            response = await self._http.request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                files=files,
                headers=headers,
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
