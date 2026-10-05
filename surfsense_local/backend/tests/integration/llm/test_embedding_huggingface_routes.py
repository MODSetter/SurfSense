"""Finding an embedder on Hugging Face, downloading it, and locking it.

Hugging Face is faked at its HTTP boundary; the model's own checks after the
download are faked at `verify`, which the unit tests and the real-model tests
cover.
"""

import json

import httpx
import pytest
from httpx import AsyncClient

from modules.embedding.huggingface import hub
from modules.llm.catalog.local.dependencies import get_local_catalog
from tests.integration.llm.installs import wait_for_end

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

REPO = "intfloat/multilingual-e5-small"
REV = "c" * 40
INSTALLED_AS = "hf--intfloat--multilingual-e5-small"
TREE = [
    {
        "type": "file",
        "path": "onnx/model.onnx",
        "size": 470_000_000,
        "lfs": {"oid": "1" * 64},
    },
    {
        "type": "file",
        "path": "onnx/model_int8.onnx",
        "size": 118_000_000,
        "lfs": {"oid": "2" * 64},
    },
    {
        "type": "file",
        "path": "onnx/model_O4.onnx",
        "size": 235_000_000,
        "lfs": {"oid": "3" * 64},
    },
    {
        "type": "file",
        "path": "tokenizer.json",
        "size": 17_000_000,
        "lfs": {"oid": "4" * 64},
    },
    {"type": "file", "path": "config.json", "size": 700},
    {"type": "file", "path": "1_Pooling/config.json", "size": 200},
    {"type": "file", "path": "modules.json", "size": 300},
    {"type": "file", "path": "config_sentence_transformers.json", "size": 200},
    {"type": "file", "path": "sentence_bert_config.json", "size": 60},
]
CONFIGS = {
    "config.json": {"hidden_size": 384, "max_position_embeddings": 512},
    "1_Pooling/config.json": {"pooling_mode_mean_tokens": True},
    "modules.json": [{"type": "sentence_transformers.models.Normalize"}],
    "config_sentence_transformers.json": {
        "prompts": {"query": "query: ", "passage": "passage: "}
    },
    "sentence_bert_config.json": {"max_seq_length": 512},
}


def build_of(body: dict) -> dict:
    """The one build an opened repo offers."""
    (build,) = body["row"]["builds"]
    return build


def fake_hub(
    *, scan: list | None = None, tree: list | None = None
) -> httpx.MockTransport:
    """Hugging Face's API and file server, answering for one repo."""

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/models" and request.url.params.get("pipeline_tag"):
            tag = request.url.params["pipeline_tag"]
            found = {
                "sentence-similarity": [
                    {"id": REPO, "downloads": 900, "gated": False, "pipeline_tag": tag}
                ],
                "feature-extraction": [
                    {
                        "id": "BAAI/bge-m3",
                        "downloads": 5000,
                        "gated": False,
                        "pipeline_tag": tag,
                    }
                ],
            }
            return httpx.Response(200, json=found.get(tag, []))
        if path == f"/api/models/{REPO}":
            return httpx.Response(
                200,
                json={
                    "sha": REV,
                    "pipeline_tag": "sentence-similarity",
                    "gated": False,
                    "securityRepoStatus": {
                        "scansDone": True,
                        "filesWithIssues": scan or [],
                    },
                },
            )
        if path == f"/api/models/{REPO}/tree/{REV}":
            return httpx.Response(200, json=tree if tree is not None else TREE)
        prefix = f"/{REPO}/resolve/{REV}/"
        if path == f"{prefix}tokenizer.json":
            return httpx.Response(200, content=b'{"model": {}}')
        if path.startswith(prefix) and path[len(prefix) :] in CONFIGS:
            return httpx.Response(200, content=json.dumps(CONFIGS[path[len(prefix) :]]))
        return httpx.Response(404)

    return httpx.MockTransport(handle)


@pytest.fixture
def huggingface(monkeypatch: pytest.MonkeyPatch):
    """Hugging Face as the fake above, with consent already given."""
    monkeypatch.setattr("modules.egress.service.require", lambda *a, **k: None)

    def use(**kwargs):
        monkeypatch.setattr(hub, "transport", lambda: fake_hub(**kwargs))

    use()
    return use


@pytest.fixture
def downloads(monkeypatch: pytest.MonkeyPatch):
    """Downloads that write a few bytes, and checks that answer as told."""
    from modules.llm.catalog.local.install import download as download_module
    from modules.llm.providers.types import DownloadProgress

    async def download(url, destination, *, sha256=None, transport=None):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"onnx")
        yield DownloadProgress("complete", 4, 4)

    monkeypatch.setattr(download_module, "download_gguf", download)
    outcome = {"width": 384, "refusal": None}
    monkeypatch.setattr(
        "modules.llm.catalog.local.engines.onnxruntime.engine.verify",
        lambda spec: (outcome["width"], outcome["refusal"]),
    )
    get_local_catalog.cache_clear()
    return outcome


async def test_search_lists_embedders_most_downloaded_first(
    client: AsyncClient, huggingface
) -> None:
    """Both tags an embedder carries, merged."""
    reply = await client.get("/embedding/huggingface/search", params={"q": "e5"})

    assert reply.status_code == 200
    assert [hit["repo"] for hit in reply.json()["results"]] == ["BAAI/bge-m3", REPO]


async def test_a_runnable_repo_resolves_to_a_build_and_what_it_will_be(
    client: AsyncClient, huggingface
) -> None:
    """A catalog row with one build: what Download fetches, and how big it is."""
    reply = await client.get(f"/embedding/huggingface/repo/{REPO}")

    body = reply.json()
    assert reply.status_code == 200, body
    assert body["row"]["runnable"] and body["row"]["not_runnable_reason"] is None
    assert body["row"]["engine"] == "onnxruntime"
    build = build_of(body)
    assert build["footprint_bytes"] == 118_000_000 + 17_000_000
    assert build["catalog_id"] and build["installed_as"] is None


async def test_a_repo_without_onnx_says_why_it_cannot_run(
    client: AsyncClient, huggingface
) -> None:
    """Safetensors alone needs torch, which the API does not ship."""
    huggingface(tree=[f for f in TREE if not f["path"].endswith(".onnx")])

    body = (await client.get(f"/embedding/huggingface/repo/{REPO}")).json()

    assert not body["row"]["runnable"]
    assert "ONNX" in body["row"]["not_runnable_reason"]
    assert body["row"]["builds"] == []


async def test_a_tokenizer_stored_without_lfs_is_hashed_from_its_bytes(
    client: AsyncClient, huggingface
) -> None:
    """Small files skip LFS, so Hugging Face lists no sha256 for them; the
    sentence-transformers repos store tokenizer.json that way."""
    small = [
        {"type": "file", "path": "tokenizer.json", "size": 700_000}
        if f["path"] == "tokenizer.json"
        else f
        for f in TREE
    ]
    huggingface(tree=small)

    body = (await client.get(f"/embedding/huggingface/repo/{REPO}")).json()

    assert body["row"]["runnable"], body
    assert build_of(body)["footprint_bytes"] == 118_000_000 + 700_000


async def test_a_repo_hugging_face_flags_is_refused(
    client: AsyncClient, huggingface
) -> None:
    """Hugging Face's own scan found malware: no download, and the screen says why."""
    huggingface(scan=[{"path": "danger.pkl", "level": "unsafe"}])

    body = (await client.get(f"/embedding/huggingface/repo/{REPO}")).json()

    assert not body["row"]["runnable"]
    assert "security scan" in body["row"]["not_runnable_reason"]


async def test_a_pick_that_passes_its_checks_installs_and_can_be_locked(
    unlocked_client: AsyncClient, huggingface, downloads, llamacpp_server
) -> None:
    """Downloaded, checked, listed, then fixed as the library's embedder."""
    client = unlocked_client
    resolved = (await client.get(f"/embedding/huggingface/repo/{REPO}")).json()

    started = await client.post(
        "/llm/installs",
        json={"catalog_id": build_of(resolved)["catalog_id"], "select": False},
    )
    job = await wait_for_end(client, started.json()["id"])

    assert job["event"]["type"] == "complete", job
    assert job["event"]["code"] == "ready"
    # Opened again, the search offers Use rather than a second download.
    reopened = (await client.get(f"/embedding/huggingface/repo/{REPO}")).json()
    assert build_of(reopened)["installed_as"] == INSTALLED_AS
    rows = (await client.get("/llm/catalog/local")).json()["rows"]
    (row,) = [r for r in rows if r["id"] == INSTALLED_AS]
    assert row["builds"][0]["installed_as"] == INSTALLED_AS
    await client.put(
        "/llm/selection/text_gen",
        json={"provider": "llamacpp", "name": "Qwen3-1.7B-Q4_K_M"},
    )
    finished = await client.post(
        "/llm/onboarding", json={"embedding_model": INSTALLED_AS}
    )
    assert finished.status_code == 200, finished.text
    active = (await client.get("/embedding/index")).json()["active"]
    spec = active["spec"]
    # Named by its repo: the install name is ours, not something a person chose.
    assert active["name"] == REPO
    assert (spec["source"], spec["identified"]) == ("huggingface", "declared")
    assert spec["query_prefix"] == "query: "


async def test_a_pick_that_fails_its_checks_is_removed(
    client: AsyncClient, huggingface, downloads, data_dir
) -> None:
    """A chat model served as an embedder ranks decoys first."""
    downloads["refusal"] = "It found 6 of 10 answers first."
    resolved = (await client.get(f"/embedding/huggingface/repo/{REPO}")).json()

    started = await client.post(
        "/llm/installs",
        json={"catalog_id": build_of(resolved)["catalog_id"], "select": False},
    )
    job = await wait_for_end(client, started.json()["id"])

    assert job["event"]["type"] == "error"
    # Its counts are in the sentence, which has no code yet.
    assert job["event"]["code"] is None
    assert "6 of 10" in json.dumps(job["event"])
    assert not (data_dir / "embeddings" / INSTALLED_AS).exists()
