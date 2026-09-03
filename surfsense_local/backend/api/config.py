from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API process, read from the environment."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    host: str = "127.0.0.1"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once, not per dependency call."""
    return Settings()
