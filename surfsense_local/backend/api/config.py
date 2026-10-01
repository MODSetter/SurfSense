from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API process, read from the environment."""

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    host: str = "127.0.0.1"
    port: int = 8000
    # Electron's main process, above every sidecar and window process: the root
    # of what the usage panel counts as the app. Unset outside Electron.
    shell_pid: int | None = None


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once, not per dependency call."""
    return Settings()
