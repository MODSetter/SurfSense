"""`GET /system/usage` against the real process table.

A Python process stands in for the Electron shell and starts a child that
stands in for a sidecar, so the tree walk and the naming run on real
processes. Its own tree, not the test runner's: the runner's other children
are not this test's to count. The graphics reader is replaced: which card a CI
host has is not what these tests are about.
"""

import subprocess
import sys
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import suppress

import psutil
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine as Database

from api.main import create_app
from modules.resource_usage.dependencies import get_resource_sampler
from modules.resource_usage.engines import Engine
from modules.resource_usage.gpu import NoGpuReader
from modules.resource_usage.sampler import ResourceSampler
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


SIDECAR = "import time; time.sleep(60)"
SHELL = (
    "import subprocess, sys, time; "
    f"subprocess.Popen([sys.executable, '-c', {SIDECAR!r}]); "
    "time.sleep(60)"
)


@pytest.fixture
def shell() -> Iterator[psutil.Process]:
    """A shell whose whole tree is Python: itself, and one sidecar under it."""
    root = psutil.Process(subprocess.Popen([sys.executable, "-c", SHELL]).pid)
    try:
        # Wait until the sidecar is listed; a Windows venv adds launchers.
        deadline = time.monotonic() + 15
        while not any(SIDECAR in " ".join(p.cmdline()) for p in _tree(root)):
            assert time.monotonic() < deadline, "the sidecar never started"
            time.sleep(0.1)
        yield root
    finally:
        for process in [*_tree(root), root]:
            with suppress(psutil.NoSuchProcess):
                process.kill()


def _tree(root: psutil.Process) -> list[psutil.Process]:
    try:
        return root.children(recursive=True)
    except psutil.NoSuchProcess:
        return []


@pytest.fixture
async def shell_client(
    engine: Database, shell: psutil.Process
) -> AsyncIterator[AsyncClient]:
    """The app rooted at that shell, with no graphics reader."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    sampler = ResourceSampler(shell.pid, Engine.INTERFACE, NoGpuReader())
    app.dependency_overrides[get_resource_sampler] = lambda: sampler
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


def engine_row(body: dict, name: str) -> dict:
    """The row the panel shows for one engine."""
    return next(row for row in body["engines"] if row["engine"] == name)


async def test_a_sidecar_under_the_shell_is_counted_as_the_app(shell_client) -> None:
    """The shell is the interface, and everything under it is named by its branch."""
    response = await shell_client.get("/system/usage")

    assert response.status_code == 200
    body = response.json()
    assert engine_row(body, "interface")["processes"] == 1
    backend = engine_row(body, "backend")
    assert backend["processes"] >= 1
    assert backend["memory_bytes"] > 0


async def test_the_machine_figures_frame_the_apps_share(shell_client) -> None:
    """The app's share never exceeds what is in use, nor that the total."""
    body = (await shell_client.get("/system/usage")).json()

    memory = body["memory"]
    assert 0 < memory["app_bytes"] <= memory["used_bytes"] <= memory["total_bytes"]
    assert 0.0 <= body["cpu"]["percent"] <= 100.0
    assert 0.0 <= body["cpu"]["app_percent"] <= 100.0
    assert body["gpus"] == []


async def test_every_engine_is_listed_so_the_panel_can_say_not_running(
    shell_client,
) -> None:
    """Engines with no process still get a row, and no graphics reader means unknown."""
    body = (await shell_client.get("/system/usage")).json()

    assert [row["engine"] for row in body["engines"]] == [
        "llamacpp",
        "sdcpp",
        "audiocpp",
        "backend",
        "interface",
    ]
    assert engine_row(body, "llamacpp")["processes"] == 0
    assert engine_row(body, "llamacpp")["gpu_memory_bytes"] is None


async def test_without_a_shell_the_api_reports_itself(client: AsyncClient) -> None:
    """A bare `python main.py` has no Electron above it; the API is the app."""
    body = (await client.get("/system/usage")).json()

    backend = engine_row(body, "backend")
    assert backend["processes"] >= 1
    assert backend["memory_bytes"] > 0
