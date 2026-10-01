"""What the screen may say about the chosen image model: chosen and waiting for
Studio, running, or unable to start. Asking never starts sd-server."""

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from httpx import AsyncClient

from modules.llm.providers import sdcpp
from shared.config import get_llm_settings

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

SDXL = "sd_xl_base_1.0_0_Q4_0"


@pytest.fixture
def sd_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """A running sd-server; the test sets which weights it was launched on."""
    serving: list[str] = []

    class Models(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps([{"filename": name} for name in serving]).encode()
            self.send_response(200 if self.path == "/sdapi/v1/sd-models" else 404)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            """Keep the request log out of the test output."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Models)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(
        get_llm_settings(), "image_base_url", f"http://127.0.0.1:{server.server_port}"
    )
    yield serving
    server.shutdown()
    server.server_close()


@pytest.fixture
def sd_server_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing listening where sd-server would: it has not been started."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setattr(
        get_llm_settings(), "image_base_url", f"http://127.0.0.1:{port}"
    )


async def choose_sdxl(client: AsyncClient, images_dir: Path) -> Path:
    """SDXL on disk and chosen for images; its weights, to remove one."""
    weights = images_dir / f"{SDXL}.gguf"
    weights.write_bytes(b"GGUF")
    chosen = await client.put(
        "/llm/selection/image_gen",
        json={"provider": sdcpp.PROVIDER, "connection_id": None, "name": SDXL},
    )
    assert chosen.status_code == 200, chosen.text
    return weights


async def state(client: AsyncClient, slot: str = "image_gen") -> str:
    """What the screen would be told for this slot."""
    reply = await client.get("/llm/image/local/state", params={"model_type": slot})
    assert reply.status_code == 200, reply.text
    return reply.json()["state"]


async def test_nothing_chosen_says_so(
    client: AsyncClient, images_dir: Path, sd_server_down: None
) -> None:
    """No local image model for the slot, so nothing to report on."""
    assert await state(client) == "none"


async def test_a_chosen_model_waits_until_studio_needs_it(
    client: AsyncClient, images_dir: Path, sd_server_down: None
) -> None:
    """Lazy start is deliberate, so not running yet is not a fault."""
    await choose_sdxl(client, images_dir)

    assert await state(client) == "idle"


async def test_a_model_sd_server_was_launched_on_is_running(
    client: AsyncClient, images_dir: Path, sd_server: list[str]
) -> None:
    """sd-server names the weights it was launched on."""
    await choose_sdxl(client, images_dir)
    sd_server.append(f"{SDXL}.gguf")

    assert await state(client) == "running"


async def test_sd_server_on_another_model_is_not_this_one_running(
    client: AsyncClient, images_dir: Path, sd_server: list[str]
) -> None:
    """Its OpenAI routes answer whatever it holds; only the filename says which."""
    await choose_sdxl(client, images_dir)
    sd_server.append("flux-2-klein-4b-Q4_K_M.gguf")

    assert await state(client) == "idle"


async def test_a_chosen_model_whose_weights_are_gone_cannot_start(
    client: AsyncClient, images_dir: Path, sd_server_down: None
) -> None:
    """Today indistinguishable from working: Electron silently starts nothing."""
    weights = await choose_sdxl(client, images_dir)
    weights.unlink()

    assert await state(client) == "missing"


async def test_asking_does_not_start_sd_server(
    client: AsyncClient, images_dir: Path, sd_server_down: None
) -> None:
    """Electron starts it only when the runtime route names files."""
    await choose_sdxl(client, images_dir)

    await state(client)

    runtime = await client.get("/llm/image/local/runtime")
    assert runtime.json()["files"] == []
