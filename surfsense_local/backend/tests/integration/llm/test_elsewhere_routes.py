"""Chat models other apps downloaded, through the routes the screens call.

The home folder is built in tmp_path the way each app writes its own folder;
no real home is read. Egress stays off throughout, because none of this reaches
a host: listing, picking and using a model are all reads of this computer.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.catalog.local.engines.llamacpp.elsewhere.looking import (
    Surroundings,
)
from modules.llm.providers.llamacpp import PRESET_FILE
from shared.config import get_llm_settings
from tests.integration.llm.conftest import INSTALLED
from tests.integration.llm.installs import install_to_end
from tests.unit.llm.catalog.local.engines.llamacpp.elsewhere.files import (
    chat_model_bytes,
    ollama_store,
    write_chat_model,
    write_embedder,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

ELSEWHERE = "/llm/catalog/local/elsewhere"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A Linux home folder SurfSense looks in, with nothing in it yet."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(
        "modules.llm.catalog.local.dependencies.this_computer",
        lambda: Surroundings(home, {}, "linux"),
    )
    get_local_catalog.cache_clear()
    return home


@pytest.fixture
def qwen_in_ollama(home: Path) -> Path:
    """qwen3:8b, pulled with Ollama into its default folder."""
    blob, _ = ollama_store(
        home / ".ollama" / "models", "qwen3", "8b", chat_model_bytes()
    )
    return blob


async def _found_row(client: AsyncClient) -> dict:
    (row,) = (await client.get(ELSEWHERE)).json()["rows"]
    return row


async def _use(client: AsyncClient, row: dict) -> dict:
    # The router lists a model once the rewritten preset names it.
    INSTALLED.append("ollama-qwen3-8b")
    return await install_to_end(
        client, catalog_id=row["builds"][0]["catalog_id"], select=True
    )


async def test_an_ollama_model_is_offered_with_nothing_to_download(
    client: AsyncClient, llamacpp_server: str, qwen_in_ollama: Path
) -> None:
    """A model Ollama pulled is listed as a chat model to use, priced for this machine."""
    body = (await client.get(ELSEWHERE)).json()

    assert (body["available"], body["look"], body["looked_in"]) == (
        True,
        True,
        ["ollama"],
    )
    (row,) = body["rows"]
    assert (row["name"], row["origin"], row["runnable"]) == (
        "qwen3:8b",
        "elsewhere",
        True,
    )
    assert row["found_in"]["app"] == "ollama"
    assert row["found_in"]["path"] == str(qwen_in_ollama)
    (build,) = row["builds"]
    assert build["catalog_id"]
    assert build["installed_as"] is None
    assert build["fit"] is not None


async def test_using_a_found_model_needs_no_egress_and_selects_it(
    client: AsyncClient, llamacpp_server: str, qwen_in_ollama: Path
) -> None:
    """Use records the file, points the runtime at it, selects it, and asks no host."""
    before = qwen_in_ollama.read_bytes()

    job = await _use(client, await _found_row(client))

    assert job["event"]["type"] == "complete", job
    assert job["event"]["selection"]["name"] == "ollama-qwen3-8b"
    models = get_llm_settings().llamacpp_models_dir
    assert f"model = {qwen_in_ollama}" in (models / PRESET_FILE).read_text()
    assert qwen_in_ollama.read_bytes() == before
    rows = (await client.get("/llm/catalog/local")).json()["rows"]
    (mine,) = [r for r in rows if r["origin"] == "elsewhere"]
    assert mine["builds"][0]["installed_as"] == "ollama-qwen3-8b"
    assert mine["builds"][0]["selected"] is True
    (listed,) = (await client.get(ELSEWHERE)).json()["rows"]
    assert listed["builds"][0]["installed_as"] == "ollama-qwen3-8b"
    assert listed["lead"]["why"] == "in_use"


async def test_removing_a_model_used_in_place_never_deletes_its_file(
    client: AsyncClient, llamacpp_server: str, qwen_in_ollama: Path
) -> None:
    """Deleting from SurfSense forgets the model; Ollama's blob stays where it was."""
    await _use(client, await _found_row(client))

    reply = await client.delete("/llm/models/ollama-qwen3-8b")

    assert reply.status_code == 200, reply.text
    assert reply.json()["selection_cleared"] is True
    assert qwen_in_ollama.is_file()
    (row,) = (await client.get(ELSEWHERE)).json()["rows"]
    assert row["builds"][0]["installed_as"] is None


async def test_looking_can_be_turned_off_and_added_folders_are_still_read(
    client: AsyncClient, llamacpp_server: str, qwen_in_ollama: Path, tmp_path: Path
) -> None:
    """The switch stops reading other apps' folders; a folder the person added is theirs."""
    off = (await client.put(f"{ELSEWHERE}/look", json={"look": False})).json()

    assert (off["look"], off["looked_in"], off["rows"]) == (False, [], [])

    folder = tmp_path / "D" / "models"
    write_chat_model(
        folder / "Mistral-7B-Instruct-Q4_K_M.gguf",
        architecture="llama",
        name="Mistral 7B Instruct",
    )
    added = await client.post(f"{ELSEWHERE}/folders", json={"path": str(folder)})

    assert added.status_code == 200, added.text
    body = added.json()
    assert body["folders"] == [str(folder)]
    assert [(r["name"], r["found_in"]["app"]) for r in body["rows"]] == [
        ("Mistral 7B Instruct", "folder")
    ]

    removed = await client.request(
        "DELETE", f"{ELSEWHERE}/folders", json={"path": str(folder)}
    )

    assert removed.json()["folders"] == []
    assert (folder / "Mistral-7B-Instruct-Q4_K_M.gguf").is_file()


async def test_a_picked_file_is_offered_to_use(
    client: AsyncClient, llamacpp_server: str, home: Path, tmp_path: Path
) -> None:
    """A file from the system's dialog comes back as a row its Use installs in place."""
    picked = write_chat_model(
        tmp_path / "Downloads" / "Qwen3-4B-Q5_K_M.gguf", name="Qwen3 4B"
    )

    reply = await client.post(f"{ELSEWHERE}/file", json={"path": str(picked)})

    assert reply.status_code == 200, reply.text
    row = reply.json()["row"]
    assert (row["name"], row["found_in"]["quantization"]) == ("Qwen3 4B", "Q5_K_M")
    assert row["builds"][0]["catalog_id"]


async def test_a_picked_file_once_used_stays_listed_where_no_look_reaches(
    client: AsyncClient, llamacpp_server: str, home: Path, tmp_path: Path
) -> None:
    """The list a person picked from keeps showing the model they chose."""
    picked = write_chat_model(
        tmp_path / "Downloads" / "Qwen3-4B-Q5_K_M.gguf", name="Qwen3 4B"
    )
    row = (await client.post(f"{ELSEWHERE}/file", json={"path": str(picked)})).json()
    INSTALLED.append("local-Qwen3-4B-Q5_K_M")

    job = await install_to_end(
        client, catalog_id=row["row"]["builds"][0]["catalog_id"], select=True
    )

    assert job["event"]["type"] == "complete", job
    (listed,) = (await client.get(ELSEWHERE)).json()["rows"]
    assert listed["builds"][0]["installed_as"] == "local-Qwen3-4B-Q5_K_M"
    assert listed["found_in"]["path"] == str(picked)


@pytest.mark.parametrize(
    ("write", "code"),
    [
        (lambda path: write_embedder(path), "embedder"),
        (lambda path: path.write_text("not a model"), "unreadable"),
        (lambda path: None, "not_found"),
    ],
)
async def test_a_picked_file_that_cannot_chat_is_refused_with_why(
    client: AsyncClient,
    llamacpp_server: str,
    home: Path,
    tmp_path: Path,
    write,
    code: str,
) -> None:
    """A picked file the runtime cannot chat with is refused with a code and a sentence."""
    picked = tmp_path / "picked.gguf"
    write(picked)

    reply = await client.post(f"{ELSEWHERE}/file", json={"path": str(picked)})

    assert reply.status_code == 422
    assert reply.json()["detail"]["code"] == code
    assert reply.json()["detail"]["message"]


async def test_the_docker_image_reads_nothing_outside_its_folders(
    client: AsyncClient,
    llamacpp_server: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """In the image nothing outside SurfSense's folders is read, listed or taken."""
    monkeypatch.setattr(
        "modules.llm.catalog.local.dependencies.this_computer", lambda: None
    )
    get_local_catalog.cache_clear()
    picked = write_chat_model(tmp_path / "Qwen3-4B-Q5_K_M.gguf")

    body = (await client.get(ELSEWHERE)).json()
    refused = await client.post(f"{ELSEWHERE}/file", json={"path": str(picked)})

    assert (body["available"], body["rows"]) == (False, [])
    assert refused.status_code == 422
