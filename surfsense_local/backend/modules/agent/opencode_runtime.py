"""An opencode running SurfSense's current configuration, ready for a turn."""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from api.config import get_settings
from api.dependencies import transact
from modules.agent.model_call_route import selected_call_route
from modules.agent.model_reads_images import selected_model_reads_images
from modules.agent.model_window import selected_model_window
from modules.agent.opencode_client import OpencodeClient
from modules.agent.opencode_config import (
    CONFIG_FILE,
    PROVIDER,
    PROVIDER_PACKAGES,
    AgentSetup,
    write_opencode_config,
)
from modules.agent.opencode_failure import opencode_failure
from modules.agent.thread_folder.repo_fence import fence_every_workspace
from shared.config import get_agent_settings, get_storage_settings

# Electron checks the file every 2 s and opencode answers about 2 s after it
# starts; the rest is room for a slow disk on the first start of a session.
READY_SECONDS = 60.0
_POLL_SECONDS = 0.25


class AgentUnavailableError(RuntimeError):
    """opencode is not part of this install, or did not start."""


@dataclass
class ReadyAgent:
    """An opencode serving the configuration just written, and the model it names."""

    client: OpencodeClient
    model: str


async def ready_opencode(
    session: Session, *, launch_key: str, earns_a_start: bool = True
) -> ReadyAgent:
    """Write opencode's configuration for the selected model, then wait until it serves it.

    The opencode already running may hold an earlier configuration, with
    another model or a launch key from a previous run; it is reloaded, and
    counts only once it reports this one. The caller closes the client.

    A turn or a new session earns an opencode Electron gave up on another
    start. A history read passes `earns_a_start=False`, so reading a failed
    turn back does not start it a second time.
    """
    settings = get_agent_settings()
    if not settings.opencode_url or not settings.opencode_password:
        raise AgentUnavailableError("the agent's runtime is not part of this install")

    await transact(session, fence_every_workspace)
    model, window = await selected_model_window(session)
    setup = AgentSetup(
        model=model,
        window=window,
        reads_images=await selected_model_reads_images(session),
        endpoint_url=_endpoint_url(),
        launch_key=launch_key,
        route=await transact(session, selected_call_route),
    )
    agent_dir = get_storage_settings().agent_dir
    config = agent_dir / CONFIG_FILE
    await run_in_threadpool(write_opencode_config, config, setup)
    if (
        earns_a_start
        and opencode_failure(agent_dir, config.stat().st_mtime) is not None
    ):
        # Electron starts opencode again only for a newer file, and an unchanged one is not rewritten.
        os.utime(config)
    written = config.stat().st_mtime

    client = OpencodeClient(settings.opencode_url, settings.opencode_password)
    try:
        await _until_serving(client, setup, agent_dir, written)
    except BaseException:
        await client.close()
        raise
    return ReadyAgent(client=client, model=model)


def connect_opencode() -> OpencodeClient:
    """A client for the opencode Electron runs, for a call that needs no new configuration.

    Answering an approval or deleting a session reaches the server as it is; only
    a turn writes the configuration first (`ready_opencode`).
    """
    settings = get_agent_settings()
    if not settings.opencode_url or not settings.opencode_password:
        raise AgentUnavailableError("the agent's runtime is not part of this install")
    return OpencodeClient(settings.opencode_url, settings.opencode_password)


def _endpoint_url() -> str:
    """This API's model endpoint, where opencode's only provider points."""
    api = get_settings()
    return f"http://{api.host}:{api.port}/agent/model/v1"


async def _until_serving(
    client: OpencodeClient, setup: AgentSetup, agent_dir: Path, written: float
) -> None:
    """Return once opencode reports `setup`, reloading it once if it holds an older one.

    Fails at once when Electron gave up on opencode after `written`.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + READY_SECONDS
    reloaded = False
    while True:
        try:
            await client.require_pinned_version()
            if _serves(await client.config(), setup):
                return
            if not reloaded:
                await client.reload_config()
                reloaded = True
        except httpx.HTTPError:
            pass  # not yet started by Electron, or still starting
        if (reason := opencode_failure(agent_dir, written)) is not None:
            raise AgentUnavailableError(f"opencode could not stay up: {reason}")
        if loop.time() > deadline:
            raise AgentUnavailableError(
                "opencode did not start with SurfSense's configuration"
            )
        await asyncio.sleep(_POLL_SECONDS)


def _serves(config: dict[str, Any], setup: AgentSetup) -> bool:
    """Whether a loaded configuration is this one: the provider package, the launch
    key, the model's window and image input."""
    provider = config.get("provider", {}).get(PROVIDER, {})
    model = provider.get("models", {}).get(setup.model, {})
    return (
        provider.get("npm") == PROVIDER_PACKAGES[setup.route]
        and provider.get("options", {}).get("apiKey") == setup.launch_key
        and model.get("limit", {}).get("context") == setup.window
        and model.get("attachment", False) == setup.reads_images
    )
