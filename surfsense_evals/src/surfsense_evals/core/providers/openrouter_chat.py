"""Bare OpenRouter ``chat/completions`` provider — no PDF, no plugins.

Used by ``BareLlmArm`` to measure "what does the model answer with
zero retrieval context?". Same wire shape as ``OpenRouterPdfProvider``
minus the file-parser plugin and the ``file`` content part:

```json
{
  "model": "openai/gpt-5.4-mini",
  "messages": [
    {"role": "system", "content": "<optional>"},
    {"role": "user",   "content": "<prompt>"}
  ]
}
```

The response shape is identical to the PDF provider's, so we re-use
``_parse_chat_completion`` from ``openrouter_pdf`` and only specialise
the request builder. That keeps cost-extraction, token-counting, and
content-array handling in one place.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .openrouter_pdf import (
    OpenRouterResponse,
    _DEFAULT_HEADERS,
    _parse_chat_completion,
)

logger = logging.getLogger(__name__)


class OpenRouterChatProvider:
    """Stateless bare-chat client. No PDF, no file-parser plugin."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str,
        timeout_s: float = 600.0,
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for the bare-LLM arm.")
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = httpx.Timeout(timeout_s, connect=15.0)

    @property
    def model(self) -> str:
        return self._model

    def _build_payload(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {"model": self._model, "messages": messages}
        if max_tokens:
            body["max_tokens"] = max_tokens
        return body

    async def complete(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> OpenRouterResponse:
        """Single chat completion. Errors are raised verbatim — caller decides retries."""

        payload = self._build_payload(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            **_DEFAULT_HEADERS,
        }
        url = f"{self._base}/chat/completions"
        started = time.monotonic()
        if http is not None:
            response = await http.post(url, json=payload, headers=headers, timeout=self._timeout)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=self._timeout
                )
        latency_ms = int((time.monotonic() - started) * 1000)
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"OpenRouter HTTP {response.status_code}: {response.text[:300]}",
                request=response.request,
                response=response,
            )
        return _parse_chat_completion(response.json(), latency_ms=latency_ms)


__all__ = ["OpenRouterChatProvider"]
