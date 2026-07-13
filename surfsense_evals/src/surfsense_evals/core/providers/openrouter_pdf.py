"""Native-PDF arm provider: OpenRouter ``chat/completions`` with PDF input.

Per `<https://openrouter.ai/docs/features/multimodal/pdfs>`__ the wire
shape is OpenAI-compatible with one PDF-specific extra:

```json
{
  "model": "anthropic/claude-sonnet-4.5",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "file", "file": {"filename": "case.pdf",
        "file_data": "data:application/pdf;base64,<b64>"}},
      {"type": "text", "text": "<prompt>"}
    ]
  }],
  "plugins": [{"id": "file-parser", "pdf": {"engine": "native"}}]
}
```

``engine: "native"`` is the only engine that doesn't pre-OCR the
PDF — it forwards raw bytes to PDF-native models (Claude, Gemini),
matching what a human user does when "dropping the PDF into Claude".
``mistral-ocr`` and ``cloudflare-ai`` are exposed as enum options for
non-native models.

Headers ``HTTP-Referer`` and ``X-Title`` make spend show up cleanly on
the OpenRouter dashboard.
"""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PdfEngine(StrEnum):
    NATIVE = "native"
    MISTRAL_OCR = "mistral-ocr"
    CLOUDFLARE_AI = "cloudflare-ai"


@dataclass
class OpenRouterResponse:
    """Subset of the OpenRouter response we care about for scoring."""

    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_micros: int
    latency_ms: int
    finish_reason: str | None
    raw: dict[str, Any]


_DEFAULT_HEADERS = {
    "HTTP-Referer": "https://github.com/MODSetter/SurfSense",
    "X-Title": "SurfSense-evals",
}


class OpenRouterPdfProvider:
    """Thin httpx-based client. Stateless; safe to reuse per arm instance."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str,
        engine: PdfEngine = PdfEngine.NATIVE,
        timeout_s: float = 600.0,
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for the native arm.")
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._model = model
        self._engine = engine
        self._timeout = httpx.Timeout(timeout_s, connect=15.0)

    @property
    def model(self) -> str:
        return self._model

    @property
    def engine(self) -> PdfEngine:
        return self._engine

    def _build_payload(
        self,
        *,
        prompt: str,
        pdf_path: Path,
        max_tokens: int | None,
        extra_messages: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
        user_content: list[dict[str, Any]] = [
            {
                "type": "file",
                "file": {
                    "filename": pdf_path.name,
                    "file_data": f"data:application/pdf;base64,{b64}",
                },
            },
            {"type": "text", "text": prompt},
        ]
        messages: list[dict[str, Any]] = list(extra_messages or [])
        messages.append({"role": "user", "content": user_content})
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "plugins": [
                {"id": "file-parser", "pdf": {"engine": self._engine.value}}
            ],
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        return body

    async def complete(
        self,
        *,
        prompt: str,
        pdf_path: Path,
        max_tokens: int | None = None,
        extra_messages: list[dict[str, Any]] | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> OpenRouterResponse:
        """Single chat completion. Errors are raised verbatim — runner decides retries."""

        payload = self._build_payload(
            prompt=prompt,
            pdf_path=pdf_path,
            max_tokens=max_tokens,
            extra_messages=extra_messages,
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
        data = response.json()
        return _parse_chat_completion(data, latency_ms=latency_ms)


def _parse_chat_completion(payload: dict[str, Any], *, latency_ms: int) -> OpenRouterResponse:
    """Tolerant parser for OpenRouter / OpenAI chat-completions JSON.

    OpenRouter passes through any provider-specific extras, but the
    canonical shape is ``choices[0].message.content`` (string OR array
    of content parts) and ``usage.prompt_tokens / completion_tokens / total_tokens``.
    Cost lives at the top level (``payload["usage"]["cost"]`` or
    ``payload["x-or-cost"]``) depending on routing.
    """

    text = ""
    finish_reason: str | None = None
    choices = payload.get("choices") or []
    if choices:
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            chunks: list[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") in {"text", "output_text"}:
                    chunks.append(str(part.get("text", "")))
            text = "".join(chunks)
        finish_reason = (choices[0] or {}).get("finish_reason") or None

    usage = payload.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))

    # OpenRouter exposes cost in dollars on `usage.cost` or `cost`. We
    # convert to integer micros to avoid float-summing surprises across
    # 7,663 MIRAGE questions.
    raw_cost = usage.get("cost")
    if raw_cost is None:
        raw_cost = payload.get("cost")
    cost_micros = 0
    if raw_cost is not None:
        try:
            cost_micros = int(round(float(raw_cost) * 1_000_000))
        except (TypeError, ValueError):
            cost_micros = 0

    return OpenRouterResponse(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_micros=cost_micros,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        raw=payload,
    )


__all__ = ["OpenRouterPdfProvider", "OpenRouterResponse", "PdfEngine"]
