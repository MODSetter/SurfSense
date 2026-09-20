import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm import providers as registry
from modules.llm.activity import model_activity, model_key
from modules.llm.catalog.dependencies import get_catalog_service
from modules.llm.providers.types import Message, Model
from modules.workspaces.models import Workspace
from shared.config import get_llm_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


async def test_providers_report_health_and_capability(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """The download UI is shown by capability, not by a provider's name."""
    body = (await client.get("/llm/providers")).json()

    local = next(entry for entry in body if entry["name"] == "llamacpp")
    assert local["healthy"] is True
    assert local["can_download"] is True


async def test_installed_models_carry_their_capabilities(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """A chosen model has to be one the runtime actually holds."""
    body = (await client.get("/llm/providers/llamacpp/models")).json()

    assert {model["name"] for model in body} == {"Qwen3-1.7B-Q4_K_M", "Qwen3-4B-Q4_K_M"}
    assert "completion" in body[0]["capabilities"]


async def test_an_unknown_provider_is_a_404(client: AsyncClient) -> None:
    """A path names a provider the registry does not have."""
    assert (await client.get("/llm/providers/openai/models")).status_code == 404


async def test_the_selection_is_read_after_it_is_set(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """Set persists the choice; read is how the rest of the app learns it."""
    assert (await client.get("/llm/selection/generation")).status_code == 404

    written = await client.put(
        "/llm/selection/generation",
        json={"provider": "llamacpp", "name": "Qwen3-4B-Q4_K_M"},
    )
    assert written.status_code == 200
    assert written.json()["name"] == "Qwen3-4B-Q4_K_M"

    read = await client.get("/llm/selection/generation")
    assert read.json() == written.json()


async def test_the_selection_says_which_prompt_tier_the_model_gets(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """A 1.7B model asks for a different prompt than a hosted frontier one."""
    await client.put(
        "/llm/selection/generation",
        json={"provider": "llamacpp", "name": "Qwen3-1.7B-Q4_K_M"},
    )

    read = (await client.get("/llm/selection/generation")).json()

    assert read["tier"] == "compact"


async def test_selecting_a_chat_model_does_not_complete_onboarding(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """Use persists the chat model; Continue writes the completion marker."""
    assert (await client.get("/llm/onboarding")).json() == {"completed": False}

    await client.put(
        "/llm/selection/generation",
        json={"provider": "llamacpp", "name": "Qwen3-1.7B-Q4_K_M"},
    )
    assert (await client.get("/llm/onboarding")).json() == {"completed": False}

    completed = await client.post("/llm/onboarding")
    assert completed.status_code == 200
    assert completed.json() == {"completed": True}


async def test_onboarding_cannot_complete_without_a_chat_model(
    client: AsyncClient,
) -> None:
    """Onboarding needs a chat model chosen before it can finish."""
    reply = await client.post("/llm/onboarding")
    assert reply.status_code == 422
    assert (await client.get("/llm/onboarding")).json() == {"completed": False}


async def test_deleting_the_selected_local_model_clears_only_the_selection(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """Deleting the active model preserves completed onboarding."""
    await client.put(
        "/llm/selection/generation",
        json={"provider": "llamacpp", "name": "Qwen3-1.7B-Q4_K_M"},
    )
    assert (await client.post("/llm/onboarding")).status_code == 200

    deleted = await client.delete("/llm/models/Qwen3-1.7B-Q4_K_M")

    assert deleted.status_code == 200
    assert deleted.json() == {
        "name": "Qwen3-1.7B-Q4_K_M",
        "selection_cleared": True,
    }
    assert (await client.get("/llm/selection/generation")).status_code == 404
    assert (await client.get("/llm/onboarding")).json() == {"completed": True}
    # Disk is the inventory, and it is what the catalog reads. The router still
    # lists the model until its next restart, which the preset rewrite triggers:
    # it scans its directory once at startup and has no way to be told otherwise.
    installed = (await client.get("/llm/catalog")).json()["installed"]
    assert [row["model_id"] for row in installed] == ["Qwen3-4B-Q4_K_M"]


async def test_remote_models_cannot_be_deleted(client: AsyncClient) -> None:
    """Remote connections never enter local provider storage routes."""
    reply = await client.delete(
        "/llm/providers/openai_compatible/models/anthropic%2Fclaude-3.5-sonnet"
    )

    assert reply.status_code == 404


async def test_a_model_in_use_cannot_be_deleted(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """Deletion cannot race an active generation."""
    key = model_key("llamacpp", "Qwen3-1.7B-Q4_K_M")
    await model_activity.acquire_use(key)
    try:
        reply = await client.delete("/llm/models/Qwen3-1.7B-Q4_K_M")
    finally:
        await model_activity.release_use(key)

    assert reply.status_code == 409
    assert reply.json()["detail"] == "model is currently in use"


async def test_a_model_cannot_be_deleted_while_one_is_installing(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """One runtime mutation cannot overlap another."""
    lock = get_catalog_service().install_lock()
    await lock.acquire()
    try:
        reply = await client.delete("/llm/models/Qwen3-1.7B-Q4_K_M")
    finally:
        lock.release()

    assert reply.status_code == 409
    assert reply.json()["detail"] == "a model is already being installed"


async def test_a_model_cannot_be_deleted_while_studio_is_generating(
    client: AsyncClient, engine: Engine, llamacpp_server: str
) -> None:
    """The API sees model work running in the separate Studio worker."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Studio")
        session.add(workspace)
        session.flush()
        session.add(
            Document(
                workspace_id=workspace.id,
                title="Running artifact",
                document_type=DocumentType.ARTIFACT,
                status=DocumentStatus.PROCESSING,
                error_message=None,
                content=None,
                content_hash=None,
                dedup_key=None,
                document_metadata=None,
            )
        )
        session.commit()

    reply = await client.delete("/llm/models/Qwen3-1.7B-Q4_K_M")

    assert reply.status_code == 409
    assert (
        reply.json()["detail"] == "a model cannot be deleted while Studio is generating"
    )


async def test_choosing_again_updates_in_place(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """One row per role: the second choice replaces the first, not adds to it."""
    await client.put(
        "/llm/selection/generation", json={"provider": "llamacpp", "name": "Qwen3-1.7B-Q4_K_M"}
    )
    await client.put(
        "/llm/selection/generation", json={"provider": "llamacpp", "name": "Qwen3-4B-Q4_K_M"}
    )

    assert (await client.get("/llm/selection/generation")).json()["name"] == "Qwen3-4B-Q4_K_M"


async def test_a_selection_names_a_known_provider(client: AsyncClient) -> None:
    """A choice pointing at no provider would never resolve to a model."""
    reply = await client.put(
        "/llm/selection/generation", json={"provider": "openai", "name": "gpt-4o"}
    )
    assert reply.status_code == 422


async def test_a_selection_names_an_installed_model(
    client: AsyncClient, llamacpp_server: str
) -> None:
    """A stale or invented model name is rejected before it reaches chat."""
    reply = await client.put(
        "/llm/selection/generation",
        json={"provider": "llamacpp", "name": "does-not-exist"},
    )

    assert reply.status_code == 422
    assert reply.json()["detail"] == "model is not installed: does-not-exist"
    assert (await client.get("/llm/selection/generation")).status_code == 404


async def test_a_generation_selection_requires_completion_capability(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An installed embedding model cannot be selected to answer chat."""

    class EmbeddingOnly:
        name = "llamacpp"

        async def health(self) -> bool:
            return True

        async def models(self) -> list[Model]:
            return [Model("embedder", installed=True, capabilities=("embedding",))]

        def chat(self, model: str, messages: list[Message]):  # pragma: no cover
            raise NotImplementedError

    monkeypatch.setitem(registry.REGISTRY, "llamacpp", EmbeddingOnly)

    reply = await client.put(
        "/llm/selection/generation",
        json={"provider": "llamacpp", "name": "embedder"},
    )

    assert reply.status_code == 422
    assert reply.json()["detail"] == "model does not support generation: embedder"
    assert (await client.get("/llm/selection/generation")).status_code == 404


def _configure_llmfit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    models: list[dict[str, object]] | None = None,
) -> None:
    system = {"system": {"available_ram_gb": 16, "total_ram_gb": 16}}
    fit = {
        "models": models
        or [
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

