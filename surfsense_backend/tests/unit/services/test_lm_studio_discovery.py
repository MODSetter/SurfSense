from types import SimpleNamespace

import httpx
import pytest

from app.services.model_connection_service import ModelDiscoveryError, discover_models


def _connection(**overrides):
    values = {
        "provider": "lm_studio",
        "base_url": "http://host.docker.internal:1234/v1",
        "api_key": None,
        "extra": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _mock_responses(monkeypatch, responses):
    requests: list[tuple[str, dict[str, str]]] = []

    class FakeAsyncClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def get(self, url: str, **kwargs) -> httpx.Response:
            requests.append((url, kwargs.get("headers") or {}))
            status, payload = responses[url]
            request = httpx.Request("GET", url)
            return httpx.Response(status, request=request, json=payload)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return requests


@pytest.mark.asyncio
async def test_lm_studio_uses_native_v1_capabilities(monkeypatch) -> None:
    native_url = "http://host.docker.internal:1234/api/v1/models"
    requests = _mock_responses(
        monkeypatch,
        {
            native_url: (
                200,
                {
                    "models": [
                        {
                            "type": "llm",
                            "key": "google/gemma-4-e4b",
                            "display_name": "Gemma 4 E4B",
                            "max_context_length": 131072,
                            "loaded_instances": [
                                {"id": "instance-1", "config": {"context_length": 8192}}
                            ],
                            "capabilities": {
                                "vision": True,
                                "trained_for_tool_use": True,
                            },
                        },
                        {
                            "type": "embedding",
                            "key": "text-embedding-nomic-embed-text-v1.5",
                            "display_name": "Nomic Embed",
                            "max_context_length": 2048,
                        },
                    ]
                },
            )
        },
    )

    models = await discover_models(_connection())

    assert requests == [(native_url, {})]
    assert models[0] == {
        "model_id": "google/gemma-4-e4b",
        "display_name": "Gemma 4 E4B",
        "source": "DISCOVERED",
        "supports_chat": True,
        "supports_image_input": True,
        "supports_tools": True,
        "supports_image_generation": False,
        "max_input_tokens": 131072,
        "metadata": {
            "type": "llm",
            "key": "google/gemma-4-e4b",
            "display_name": "Gemma 4 E4B",
            "max_context_length": 131072,
            "loaded_instances": [
                {"id": "instance-1", "config": {"context_length": 8192}}
            ],
            "capabilities": {
                "vision": True,
                "trained_for_tool_use": True,
            },
        },
    }
    assert models[1]["supports_chat"] is False
    assert models[1]["supports_image_input"] is False


@pytest.mark.asyncio
async def test_lm_studio_budget_tracks_max_not_loaded_context(monkeypatch) -> None:
    """Discovery reports the model's maximum, not whatever a currently loaded
    instance happens to use — the latter changes without a rediscovery."""
    native_url = "http://host.docker.internal:1234/api/v1/models"
    _mock_responses(
        monkeypatch,
        {
            native_url: (
                200,
                {
                    "models": [
                        {
                            "type": "llm",
                            "key": "model",
                            "max_context_length": 32768,
                            "loaded_instances": [
                                {"id": "one", "config": {"context_length": 8192}}
                            ],
                        }
                    ]
                },
            )
        },
    )

    models = await discover_models(_connection())

    assert models[0]["max_input_tokens"] == 32768


@pytest.mark.asyncio
async def test_lm_studio_sends_token_to_native_discovery(monkeypatch) -> None:
    native_url = "https://lm.example.com/team/api/v1/models"
    # One model, because an empty catalog is itself a discovery failure and
    # would raise before the header assertion below.
    requests = _mock_responses(
        monkeypatch,
        {native_url: (200, {"models": [{"type": "llm", "key": "model"}]})},
    )

    await discover_models(
        _connection(
            base_url="https://lm.example.com/team/v1/",
            api_key="lm-secret",
        )
    )

    assert requests == [(native_url, {"Authorization": "Bearer lm-secret"})]


@pytest.mark.asyncio
async def test_lm_studio_falls_back_to_legacy_v0_only_when_v1_is_absent(
    monkeypatch,
) -> None:
    v1_url = "http://host.docker.internal:1234/api/v1/models"
    v0_url = "http://host.docker.internal:1234/api/v0/models"
    requests = _mock_responses(
        monkeypatch,
        {
            v1_url: (404, {"error": "not found"}),
            v0_url: (
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": "qwen2-vl-7b-instruct",
                            "type": "vlm",
                            "max_context_length": 32768,
                        }
                    ],
                },
            ),
        },
    )

    models = await discover_models(_connection())

    assert [url for url, _headers in requests] == [v1_url, v0_url]
    assert models[0]["supports_chat"] is True
    assert models[0]["supports_image_input"] is True


@pytest.mark.asyncio
async def test_lm_studio_rejects_when_native_apis_are_unavailable(
    monkeypatch,
) -> None:
    root = "http://host.docker.internal:1234"
    requests = _mock_responses(
        monkeypatch,
        {
            f"{root}/api/v1/models": (404, {"error": "not found"}),
            f"{root}/api/v0/models": (405, {"error": "method not allowed"}),
        },
    )

    with pytest.raises(
        ModelDiscoveryError,
        match=r"Upgrade LM Studio to version 0\.4 or newer",
    ):
        await discover_models(_connection())

    assert [url for url, _headers in requests] == [
        f"{root}/api/v1/models",
        f"{root}/api/v0/models",
    ]


@pytest.mark.asyncio
async def test_lm_studio_does_not_hide_native_server_errors(monkeypatch) -> None:
    native_url = "http://host.docker.internal:1234/api/v1/models"
    requests = _mock_responses(
        monkeypatch,
        {native_url: (500, {"error": "server failed"})},
    )

    with pytest.raises(
        ModelDiscoveryError, match="Model discovery failed with HTTP 500"
    ):
        await discover_models(_connection())

    assert requests == [(native_url, {})]


@pytest.mark.asyncio
async def test_lm_studio_rejects_malformed_success_without_fallback(
    monkeypatch,
) -> None:
    native_url = "http://host.docker.internal:1234/api/v1/models"
    requests = _mock_responses(
        monkeypatch,
        {native_url: (200, {"unexpected": "shape"})},
    )

    with pytest.raises(
        ModelDiscoveryError,
        match="LM Studio native v1 returned an unsupported model-list response",
    ):
        await discover_models(_connection())

    assert requests == [(native_url, {})]
