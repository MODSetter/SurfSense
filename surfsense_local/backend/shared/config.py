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
    def embedding_models_dir(self) -> Path:
        """Downloaded embedders, one folder each. Not `models_dir`, which a
        packaged app ships read-only."""
        return self.data_dir / "embeddings"

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

    def agent_working_dir(self, workspace_id: int) -> Path:
        """The workspace's agent folder: its threads' folders and their text cache.

        Before each thread had its own, every thread worked here; such a thread
        is legacy, and only its history is still read.
        """
        return self.workspace_dir(workspace_id) / "agent"

    def agent_threads_dir(self, workspace_id: int) -> Path:
        return self.agent_working_dir(workspace_id) / "threads"

    def thread_working_dir(self, workspace_id: int, thread_id: int) -> Path:
        """The folder one agent thread works in: its sources and its outputs."""
        return self.agent_threads_dir(workspace_id) / str(thread_id)

    def agent_text_dir(self, workspace_id: int) -> Path:
        """One file per source text version, hard-linked into each thread that uses it."""
        return self.agent_working_dir(workspace_id) / "text"

    @property
    def agent_dir(self) -> Path:
        """Electron watches here for opencode's configuration and keeps opencode's home."""
        return self.data_dir / "agent"

    def plugin_dir(self, plugin_id: str, version: str) -> Path:
        """Where one installed version of a plugin lives."""
        return self.data_dir / "plugins" / plugin_id / version

    def plugin_data_dir(self, plugin_id: str) -> Path:
        """A plugin's own files, which outlive the versions that wrote them."""
        return self.data_dir / "plugins" / plugin_id / "data"


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
    audio_base_url: str = "http://127.0.0.1:8082"
    audio_models_dir: Path | None = None
    # The eSpeak-ng staged beside the server, which the API names in server.json
    # for the families that do not read it from the server's environment.
    audio_espeak_library: Path | None = None
    audio_espeak_data: Path | None = None


class AgentSettings(BaseSettings):
    """Where opencode will listen and its password, chosen by Electron at boot.

    Both unset where no opencode is staged, and then the agent is not offered.
    """

    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_")

    opencode_url: str | None = None
    opencode_password: str | None = None
    # A developer's switch: SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1 makes Agentic the
    # default for every model the user has not picked a mode for, and lifts the
    # window floor; a stated no on tool calls, or no opencode, still keeps it out.
    agent_untested_models: bool = False

    def has_opencode(self) -> bool:
        """Whether Electron runs an opencode beside this API: it passes both only then."""
        return bool(self.opencode_url and self.opencode_password)


@lru_cache
def get_agent_settings() -> AgentSettings:
    """Cached so the environment is parsed once, not per turn."""
    return AgentSettings()


@lru_cache
def get_storage_settings() -> StorageSettings:
    """Cached so the environment is parsed once, not per dependency call."""
    return StorageSettings()


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
