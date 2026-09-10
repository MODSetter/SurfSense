import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm import providers as registry
from modules.llm.activity import model_activity, model_key
from modules.llm.providers.types import Message, Model
from modules.llm.recommendations.dependencies import get_catalog_service
from modules.workspaces.models import Workspace
from shared.config import get_llm_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


async def test_providers_report_health_and_capability(
    client: AsyncClient, ollama_server: str
) -> None:
    """The download UI is shown by capability, not by a provider's name."""
    body = (await client.get("/llm/providers")).json()

    ollama = next(entry for entry in body if entry["name"] == "ollama")
    assert ollama["healthy"] is True
    assert ollama["can_download"] is True


async def test_installed_models_carry_their_capabilities(
    client: AsyncClient, ollama_server: str
) -> None:
    """A chosen model has to be one the runtime actually holds."""
    body = (await client.get("/llm/providers/ollama/models")).json()

    assert {model["name"] for model in body} == {"qwen3:1.7b", "qwen3:4b"}
    assert "tools" in body[0]["capabilities"]


async def test_the_catalog_marks_what_is_installed(
    client: AsyncClient, ollama_server: str
) -> None:
    """The offer list greys what is already here."""
    body = (await client.get("/llm/providers/ollama/catalog")).json()

    entries = {entry["name"]: entry for entry in body}
    assert entries["qwen3:1.7b"]["installed"] is True
    assert entries["qwen3:32b"]["installed"] is False


async def test_an_unknown_provider_is_a_404(client: AsyncClient) -> None:
    """A path names a provider the registry does not have."""
    assert (await client.get("/llm/providers/openai/models")).status_code == 404


async def test_pull_streams_progress(client: AsyncClient, ollama_server: str) -> None:
    """The client needs progress, not one reply after minutes of silence."""
    steps = []
    async with client.stream(
        "POST", "/llm/providers/ollama/pull", json={"name": "qwen3:1.7b"}
    ) as reply:
        assert reply.status_code == 200
        async for line in reply.aiter_lines():
            if line:
                steps.append(json.loads(line))

    assert steps[0]["status"] == "pulling manifest"
    assert steps[-1]["status"] == "success"


async def test_the_selection_is_read_after_it_is_set(
    client: AsyncClient, ollama_server: str
) -> None:
    """Set persists the choice; read is how the rest of the app learns it."""
    assert (await client.get("/llm/selection/generation")).status_code == 404

    written = await client.put(
        "/llm/selection/generation",
        json={"provider": "ollama", "name": "qwen3:4b"},
    )
    assert written.status_code == 200
    assert written.json()["name"] == "qwen3:4b"

    read = await client.get("/llm/selection/generation")
    assert read.json() == written.json()


async def test_selecting_the_first_model_completes_onboarding(
    client: AsyncClient, ollama_server: str
) -> None:
    """The first valid selection is the durable onboarding boundary."""
    assert (await client.get("/llm/onboarding")).json() == {"completed": False}

    await client.put(
        "/llm/selection/generation",
        json={"provider": "ollama", "name": "qwen3:1.7b"},
    )

    assert (await client.get("/llm/onboarding")).json() == {"completed": True}


async def test_deleting_the_selected_local_model_clears_only_the_selection(
    client: AsyncClient, ollama_server: str
) -> None:
    """Deleting the active model preserves completed onboarding."""
    await client.put(
        "/llm/selection/generation",
        json={"provider": "ollama", "name": "qwen3:1.7b"},
    )

    deleted = await client.delete("/llm/providers/ollama/models/qwen3%3A1.7b")

    assert deleted.status_code == 200
    assert deleted.json() == {
        "name": "qwen3:1.7b",
        "selection_cleared": True,
    }
    assert (await client.get("/llm/selection/generation")).status_code == 404
    assert (await client.get("/llm/onboarding")).json() == {"completed": True}
    models = (await client.get("/llm/providers/ollama/models")).json()
    assert [model["name"] for model in models] == ["qwen3:4b"]


async def test_remote_models_cannot_be_deleted(client: AsyncClient) -> None:
    """Remote connections never enter local provider storage routes."""
    reply = await client.delete(
        "/llm/providers/openai_compatible/models/anthropic%2Fclaude-3.5-sonnet"
    )

    assert reply.status_code == 404


async def test_embedding_models_cannot_be_deleted_from_chat_management(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deletion is limited to local generation models."""

    class EmbeddingStore:
        name = "embedding-store"

        async def health(self) -> bool:
            return True

        async def models(self) -> list[Model]:
            return [Model("nomic-embed-text", True, ("embedding",))]

        def catalog(self) -> list[object]:
            return []

        async def pull(self, name: str):
            if False:  # pragma: no cover - makes this an async iterator
                yield name

        async def delete(self, name: str) -> None:  # pragma: no cover
            raise AssertionError(f"must not delete {name}")

        def chat(self, model: str, messages: list[Message]):  # pragma: no cover
            raise NotImplementedError

    monkeypatch.setitem(registry.REGISTRY, "embedding-store", EmbeddingStore)

    reply = await client.delete(
        "/llm/providers/embedding-store/models/nomic-embed-text"
    )

    assert reply.status_code == 409
    assert (
        reply.json()["detail"] == "model does not support generation: nomic-embed-text"
    )


async def test_a_model_in_use_cannot_be_deleted(
    client: AsyncClient, ollama_server: str
) -> None:
    """Deletion cannot race an active generation."""
    key = model_key("ollama", "qwen3:1.7b")
    await model_activity.acquire_use(key)
    try:
        reply = await client.delete("/llm/providers/ollama/models/qwen3%3A1.7b")
    finally:
        await model_activity.release_use(key)

    assert reply.status_code == 409
    assert reply.json()["detail"] == "model is currently in use"


async def test_a_model_cannot_be_deleted_while_ollama_is_installing(
    client: AsyncClient, ollama_server: str
) -> None:
    """One runtime mutation cannot overlap another."""
    lock = get_catalog_service().install_lock("ollama")
    await lock.acquire()
    try:
        reply = await client.delete("/llm/providers/ollama/models/qwen3%3A1.7b")
    finally:
        lock.release()

    assert reply.status_code == 409
    assert reply.json()["detail"] == "ollama is currently installing a model"


async def test_a_model_cannot_be_deleted_while_studio_is_generating(
    client: AsyncClient, engine: Engine, ollama_server: str
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

    reply = await client.delete("/llm/providers/ollama/models/qwen3%3A1.7b")

    assert reply.status_code == 409
    assert (
        reply.json()["detail"] == "a model cannot be deleted while Studio is generating"
    )


async def test_choosing_again_updates_in_place(
    client: AsyncClient, ollama_server: str
) -> None:
    """One row per role: the second choice replaces the first, not adds to it."""
    await client.put(
        "/llm/selection/generation", json={"provider": "ollama", "name": "qwen3:1.7b"}
    )
    await client.put(
        "/llm/selection/generation", json={"provider": "ollama", "name": "qwen3:4b"}
    )

    assert (await client.get("/llm/selection/generation")).json()["name"] == "qwen3:4b"


async def test_a_selection_names_a_known_provider(client: AsyncClient) -> None:
    """A choice pointing at no provider would never resolve to a model."""
    reply = await client.put(
        "/llm/selection/generation", json={"provider": "openai", "name": "gpt-4o"}
    )
    assert reply.status_code == 422


async def test_a_selection_names_an_installed_model(
    client: AsyncClient, ollama_server: str
) -> None:
    """A stale or invented model name is rejected before it reaches chat."""
    reply = await client.put(
        "/llm/selection/generation",
        json={"provider": "ollama", "name": "does-not-exist"},
    )

    assert reply.status_code == 422
    assert reply.json()["detail"] == "model is not installed: does-not-exist"
    assert (await client.get("/llm/selection/generation")).status_code == 404


async def test_a_generation_selection_requires_completion_capability(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An installed embedding model cannot be selected to answer chat."""

    class EmbeddingOnly:
        name = "ollama"

        async def health(self) -> bool:
            return True

        async def models(self) -> list[Model]:
            return [Model("embedder", installed=True, capabilities=("embedding",))]

        def chat(self, model: str, messages: list[Message]):  # pragma: no cover
            raise NotImplementedError

    monkeypatch.setitem(registry.REGISTRY, "ollama", EmbeddingOnly)

    reply = await client.put(
        "/llm/selection/generation",
        json={"provider": "ollama", "name": "embedder"},
    )

    assert reply.status_code == 422
    assert reply.json()["detail"] == "model does not support generation: embedder"
    assert (await client.get("/llm/selection/generation")).status_code == 404


async def test_a_chat_only_provider_hides_the_catalog(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A remote API that cannot download offers no catalog to download from."""

    class Echo:
        name = "echo"

        async def health(self) -> bool:
            return True

        async def models(self) -> list[Model]:
            return []

        def chat(self, model: str, messages: list[Message]):  # pragma: no cover
            raise NotImplementedError

    monkeypatch.setitem(registry.REGISTRY, "echo", lambda: Echo())

    listed = (await client.get("/llm/providers")).json()
    echo = next(entry for entry in listed if entry["name"] == "echo")
    assert echo["can_download"] is False

    assert (await client.get("/llm/providers/echo/catalog")).status_code == 409


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
                "ollama_name": "qwen3:8b",
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


async def test_catalog_exposes_one_row_per_runtime_target(
    client: AsyncClient,
    ollama_server: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The API keeps the curated Qwen row when llmfit maps Base to the same tag."""
    common = {
        "provider": "Qwen",
        "parameter_count": "1.7B",
        "use_case": "general",
        "fit_level": "perfect",
        "runtime": "llamacpp",
        "run_mode": "gpu",
        "best_quant": "Q4_K_M",
        "memory_required_gb": 2,
        "memory_available_gb": 16,
        "disk_size_gb": 2,
        "effective_context_length": 8192,
        "capability_ids": ["tool_use"],
        "gguf_sources": [],
    }
    _configure_llmfit(
        tmp_path,
        monkeypatch,
        [
            {
                **common,
                "name": "Qwen/Qwen3-1.7B-Base",
                "score": 72.8,
                "ollama_name": "qwen3:1.7b",
            },
            {
                **common,
                "name": "Qwen/Qwen3-1.7B",
                "score": 69.2,
                "ollama_name": None,
            },
        ],
    )

    catalog = (await client.get("/llm/catalog")).json()

    matching = [
        row
        for section in ("recommended", "explore", "installed")
        for row in catalog[section]
        if row["runtime_model"] == "qwen3:1.7b"
    ]
    assert [row["canonical_id"] for row in matching] == ["Qwen/Qwen3-1.7B"]
    get_catalog_service.cache_clear()


async def test_ranked_catalog_installs_and_selects_in_one_stream(
    client: AsyncClient,
    ollama_server: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normalized route resolves an opaque id, installs, and persists selection."""
    _configure_llmfit(tmp_path, monkeypatch)
    catalog = (await client.get("/llm/catalog")).json()

    assert [row["canonical_id"] for row in catalog["recommended"]] == ["Qwen/Qwen3-8B"]
    catalog_id = catalog["recommended"][0]["catalog_id"]

    events = []
    async with client.stream(
        "POST",
        "/llm/install",
        json={"catalog_id": catalog_id, "select": True},
    ) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line:
                events.append(json.loads(line))

    assert [event["type"] for event in events] == [
        "starting",
        "downloading",
        "downloading",
        "downloading",
        "downloading",
        "verifying",
        "selecting",
        "complete",
    ]
    assert events[-1]["selection"]["name"] == "qwen3:8b"
    assert (await client.get("/llm/selection/generation")).json()["name"] == "qwen3:8b"
    get_catalog_service.cache_clear()


async def test_refresh_makes_old_catalog_ids_unusable(
    client: AsyncClient,
    ollama_server: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refresh revokes prior artifact choices before download starts."""
    _configure_llmfit(tmp_path, monkeypatch)
    old_id = (await client.get("/llm/catalog")).json()["recommended"][0]["catalog_id"]
    await client.get("/llm/catalog?refresh=true")

    response = await client.post(
        "/llm/install", json={"catalog_id": old_id, "select": True}
    )

    assert response.status_code == 422
    get_catalog_service.cache_clear()


async def test_missing_llmfit_keeps_installed_models_available(
    client: AsyncClient,
    ollama_server: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recommendation failure cannot hide models that can still answer chat."""
    monkeypatch.setattr(get_llm_settings(), "llmfit_path", tmp_path / "missing")
    get_catalog_service.cache_clear()

    catalog = (await client.get("/llm/catalog")).json()

    assert {row["runtime_model"] for row in catalog["installed"]} == {
        "qwen3:1.7b",
        "qwen3:4b",
    }
    assert catalog["warnings"][0]["code"] == "missing"
    get_catalog_service.cache_clear()
