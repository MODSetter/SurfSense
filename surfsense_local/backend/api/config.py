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
    # Comma-separated. "*" is what the desktop app needs: its window loads from
    # file:// and calls the loopback sidecar cross-origin. The Docker image sets
    # it empty, so no cross-origin page can talk to the API.
    cors_origins: str = "*"
    # The port a browser reaches this API's sign-in callbacks on. In the Docker
    # image `port` is inside the container and the browser comes in through the
    # published one; unset elsewhere, where the two are the same.
    public_port: int | None = None
    # Docker only: the fixed loopback port ChatGPT's sign-in listens on, which the
    # container's Caddy forwards `/callback` to. 0 picks a free port, as the desktop does.
    chatgpt_callback_port: int = 0
    # "docker" in the Docker image, where what the user installs goes in the container.
    runtime: str | None = None

    def in_container(self) -> bool:
        return self.runtime == "docker"

    def browser_port(self) -> int:
        """The port a sign-in sends the browser back to."""
        return self.public_port or self.port

    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once, not per dependency call."""
    return Settings()
