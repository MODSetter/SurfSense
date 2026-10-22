"""A git repository above the data folder, as the real opencode finds it."""

import os
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from modules.agent.thread_folder.repo_fence import FENCE
from shared.config import get_storage_settings
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_threads import open_thread, thread_folder

pytestmark = pytest.mark.integration


async def project_root(api: AgentAPI, folder: Path) -> str:
    """The project opencode resolved for the folder's instance, in one spelling."""
    async with httpx.AsyncClient(
        base_url=api.opencode_url, auth=("opencode", api.password)
    ) as http:
        reply = await http.get(
            "/api/location", params={"location[directory]": str(folder)}
        )
        reply.raise_for_status()
        return os.path.normcase(os.path.realpath(reply.json()["project"]["directory"]))


def _spelled(folder: Path) -> str:
    return os.path.normcase(os.path.realpath(folder))


async def test_a_repository_above_is_not_the_project_of_a_thread_read_before_its_next_sync(
    agent_api: AgentAPI,
) -> None:
    """opencode resolves a folder's project when its instance starts, and reading a thread's history starts it."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not on the PATH")
    thread = await open_thread(agent_api, "Research")
    folder = thread_folder(agent_api.workspace_id, thread["id"])
    subprocess.run(
        [git, "init", "-q", str(get_storage_settings().data_dir)], check=True
    )
    async with agent_api.opencode() as opencode:
        await opencode.dispose_instance(folder)

    history = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    assert history.status_code == 200
    # The thread's own folder, not the repository above it.
    assert await project_root(agent_api, folder) == _spelled(folder)


async def test_without_a_repository_above_no_fence_is_written(
    agent_api: AgentAPI,
) -> None:
    """Else every opencode start runs git, which on a Mac without the tools asks to install them."""
    thread = await open_thread(agent_api, "Research")

    agent_folder = get_storage_settings().agent_working_dir(agent_api.workspace_id)
    assert not (agent_folder / FENCE).exists()
    folder = thread_folder(agent_api.workspace_id, thread["id"])
    assert await project_root(agent_api, folder) == _spelled(folder)
