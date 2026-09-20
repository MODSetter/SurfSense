"""Nothing leaves the machine until the user allows that destination."""

import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.catalog.dependencies import get_catalog_service
from modules.llm.models import ProviderConnection
from shared.config import get_llm_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

REMOTE = {
    "label": "Cloud",
    "provider": "openai_compatible",
    "base_url": "https://api.provider.example/v1",
}


async def _destinations(client: AsyncClient) -> dict[str, dict]:
    reply = await client.get("/egress")
    assert reply.status_code == 200
    return {row["destination"]: row for row in reply.json()}


async def test_remote_connection_is_refused_before_it_is_probed(
    client: AsyncClient,
) -> None:
    """The host is named in the refusal, so the UI can ask about that host."""
    refused = await client.post("/llm/connections", json=REMOTE)
    assert refused.status_code == 403
    assert refused.json()["detail"]["destination"] == "host:api.provider.example"


async def test_stored_remote_connection_is_listed_off_and_refused(
    client: AsyncClient, engine: Engine
) -> None:
    """A connection allowed earlier and revoked later shows in the panel and is refused."""
    with create_session_factory(engine)() as session:
        session.add(ProviderConnection(**REMOTE))
        session.commit()

    assert (await _destinations(client))["host:api.provider.example"] == {
        "destination": "host:api.provider.example",
        "host": "api.provider.example",
        "enabled": False,
        "last_call_at": None,
    }
    assert (await client.get("/llm/connections/1/models")).status_code == 403


async def test_loopback_connections_are_not_egress(
    client: AsyncClient, openai_server: str
) -> None:
    """A provider on this machine needs no permission and has no panel row."""
    created = await client.post(
        "/llm/connections",
        json={**REMOTE, "label": "Local", "base_url": openai_server},
    )
    assert created.status_code == 201, created.text
    # The two weight downloads are always listed; the connection adds no third.
    assert set(await _destinations(client)) == {
        "image_model_pull",
        # One host, two consents: a repo the user named, and text they typed.
        "model_download",
        "model_search",
    }


async def test_unknown_destination_is_rejected(client: AsyncClient) -> None:
    """Only destinations the app contacts can be toggled."""
    reply = await client.put("/egress/keygen", json={"enabled": True})
    assert reply.status_code == 422


def _configure_llmfit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    system = {"system": {"available_ram_gb": 16, "total_ram_gb": 16}}
    fit = {
        "models": [
            {
                "name": "Qwen/Qwen3-8B",
                "provider": "Qwen",
                "parameter_count": "8B",
                "use_case": "chat",
                "fit_level": "good",
                "score": 85,
                "runtime": "llamacpp",
                "run_mode": "gpu",
                "best_quant": "Q4_K_M",
                "memory_required_gb": 6,
                "memory_available_gb": 16,
                "disk_size_gb": 5.2,
                "effective_context_length": 8192,
                "capability_ids": ["tool_use"],
                "file": "Qwen3-8B-Q4_K_M.gguf",
                "gguf_sources": [],
            }
        ]
    }
    executable = tmp_path / "llmfit"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"system = {json.dumps(system)!r}\n"
        f"fit = {json.dumps(fit)!r}\n"
        'print("llmfit 1.1.11" if "--version" in sys.argv '
        'else system if "system" in sys.argv else fit)\n'
    )
    executable.chmod(0o755)
    monkeypatch.setattr(get_llm_settings(), "llmfit_path", executable)
    get_catalog_service.cache_clear()

