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


class SearchSettings(BaseSettings):
    """The index's shape, which both ingest and search have to agree on."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    # Schema, not preference: a vec0 table declares its width at creation.
    # 384 is bge-small-en-v1.5, the bundled default.
    embedding_dimension: int = 384


@lru_cache
def get_storage_settings() -> StorageSettings:
    """Cached so the environment is parsed once, not per dependency call."""
    return StorageSettings()


@lru_cache
def get_search_settings() -> SearchSettings:
    return SearchSettings()
