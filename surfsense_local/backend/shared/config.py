import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    """On-disk locations, read by both the API and the worker process."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    data_dir: Path = Path.home() / ".surfsense"

    @property
    def models_dir(self) -> Path:
        # Overridable on its own so packaging can ship weights beside the app.
        override = os.environ.get("SURFSENSE_LOCAL_MODELS_DIR")
        return Path(override) if override else self.data_dir / "models"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "surfsense.db"

    @property
    def queue_path(self) -> Path:
        return self.data_dir / "huey.db"

    def document_dir(self, workspace_id: int, document_id: int) -> Path:
        """Where one document's bytes live: the original and anything derived.

        Keyed by id rather than filename, so nothing a user types reaches the
        filesystem.
        """
        return (
            self.data_dir
            / "data"
            / "workspaces"
            / str(workspace_id)
            / "documents"
            / str(document_id)
        )

    def workspace_dir(self, workspace_id: int) -> Path:
        return self.data_dir / "data" / "workspaces" / str(workspace_id)

    def artifact_dir(self, workspace_id: int, artifact_id: int) -> Path:
        """Where one artifact's rendered blobs live, keyed by id like documents."""
        return self.workspace_dir(workspace_id) / "artifacts" / str(artifact_id)


class SearchSettings(BaseSettings):
    """The index's shape, which both ingest and search have to agree on."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    # Schema, not preference: a vec0 table declares its width at creation.
    # 384 is bge-small-en-v1.5, the bundled default.
    embedding_dimension: int = 384


class LLMSettings(BaseSettings):
    """The generation runtime. Electron starts llama-server and passes its address."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    # llama-server in router mode. Electron picks the port, points the router at
    # the models directory, and passes the staged library directory: the probe
    # has to run from there, because ggml scans the running executable's own
    # directory for backends and silently finds none anywhere else.
    llamacpp_base_url: str = "http://127.0.0.1:8080"
    llamacpp_models_dir: Path | None = None
    llamacpp_library_dir: Path | None = None

    # The bundled sd-server, same arrangement: Electron picks the port and only
    # runs it once its model is downloaded. Absent models_dir means the host has
    # no sd-server build, and local image generation is simply not offered.
    image_base_url: str = "http://127.0.0.1:1234"
    image_models_dir: Path | None = None

    # The bundled audio.cpp server's folder, where its models and the
    # `server.json` Electron starts it from live. Absent means the host has no
    # audio.cpp build, and local audio models are not offered.
    audio_models_dir: Path | None = None


@lru_cache
def get_storage_settings() -> StorageSettings:
    """Cached so the environment is parsed once, not per dependency call."""
    return StorageSettings()


@lru_cache
def get_search_settings() -> SearchSettings:
    return SearchSettings()


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
