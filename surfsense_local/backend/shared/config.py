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


@lru_cache
def get_storage_settings() -> StorageSettings:
    """Cached so the environment is parsed once, not per dependency call."""
    return StorageSettings()
