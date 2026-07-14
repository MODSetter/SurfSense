"""respx-mocked tests for the OpenRouter PDF provider."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest
import respx

from surfsense_evals.core.providers.openrouter_pdf import (
    OpenRouterPdfProvider,
    PdfEngine,
)

_BASE = "https://openrouter.test"


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "case.pdf"
    p.write_bytes(b"%PDF-1.4 minimal content")
    return p


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_payload_shape_matches_openrouter_docs(respx_mock, tiny_pdf: Path):
    captured = {}

    def _capture(request):
        captured["body"] = json.loads(request.content)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": "Answer: B"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "cost": 0.0001,
                },
            },
        )

    respx_mock.post("/chat/completions").mock(side_effect=_capture)

    provider = OpenRouterPdfProvider(
        api_key="sk-or-test",
        base_url=_BASE,
        model="anthropic/claude-sonnet-4.5",
        engine=PdfEngine.NATIVE,
    )
    response = await provider.complete(prompt="What is the diagnosis?", pdf_path=tiny_pdf)
    body = captured["body"]
    assert body["model"] == "anthropic/claude-sonnet-4.5"
    assert body["plugins"] == [{"id": "file-parser", "pdf": {"engine": "native"}}]
    user = body["messages"][-1]
    assert user["role"] == "user"
    file_part = user["content"][0]
    assert file_part["type"] == "file"
    assert file_part["file"]["filename"] == tiny_pdf.name
    assert file_part["file"]["file_data"].startswith("data:application/pdf;base64,")
    assert (
        base64.b64decode(file_part["file"]["file_data"].split(",", 1)[1]) == tiny_pdf.read_bytes()  # noqa: ASYNC240 — test fixture, sync read is fine
    )
    assert user["content"][1] == {"type": "text", "text": "What is the diagnosis?"}
    assert captured["headers"]["authorization"] == "Bearer sk-or-test"
    assert captured["headers"].get("x-title") == "SurfSense-evals"

    assert response.text == "Answer: B"
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.total_tokens == 15
    # cost 0.0001 USD == 100 micros
    assert response.cost_micros == 100


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_chat_array_content_concatenates(respx_mock, tiny_pdf: Path):
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "Hello "},
                                {"type": "text", "text": "world"},
                                {"type": "image_url", "image_url": "ignored"},
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
    )
    provider = OpenRouterPdfProvider(api_key="sk-or-test", base_url=_BASE, model="x/y")
    response = await provider.complete(prompt="hi", pdf_path=tiny_pdf)
    assert response.text == "Hello world"


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_provider_raises_on_4xx(respx_mock, tiny_pdf: Path):
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"message": "rate limited"}})
    )
    provider = OpenRouterPdfProvider(api_key="sk-or-test", base_url=_BASE, model="x/y")
    with pytest.raises(httpx.HTTPStatusError):
        await provider.complete(prompt="hi", pdf_path=tiny_pdf)


def test_missing_api_key_raises():
    with pytest.raises(ValueError):
        OpenRouterPdfProvider(api_key="", base_url=_BASE, model="x/y")
