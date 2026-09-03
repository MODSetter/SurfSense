from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    """On-disk locations, read by both the API and the worker process."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    data_dir: Path = Path.home() / ".surfsense"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "surfsense.db"


class SearchSettings(BaseSettings):
    """The index's shape, which both ingest and search have to agree on."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    # Schema, not preference: a vec0 table declares its width at creation.
    # 768 is nomic-embed-text.
    embedding_dimension: int = 768


@lru_cache
def get_storage_settings() -> StorageSettings:
    """Cached so the environment is parsed once, not per dependency call."""
    return StorageSettings()


@lru_cache
def get_search_settings() -> SearchSettings:
    return SearchSettings()
