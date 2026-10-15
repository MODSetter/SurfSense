"""A ticked folder, end to end: made, filled by a folder upload, and then exactly
its sources reach chat and Studio, however many there are."""

import hashlib
import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.artifacts.models import Artifact
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from shared.db import create_session_factory
from worker.ingestion import run as ingest
from worker.studio import run as run_studio
from worker.studio.shared.artifact import Source

pytestmark = pytest.mark.integration

ANSWER = "The probe carried a generator catalogued as RTGX7."
# Past the 50 newest an id list used to carry.
FILLERS = 60


@pytest.fixture
def stub_encoder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ingest and search without the bundled model: a deterministic vector and a
    character tokenizer. The keyword leg still finds the exact term."""

    def embed(spec: Any, texts: list[str], _purpose: Any) -> list[list[float]]:
        return [[float(len(text) % 97)] * spec.dimension for text in texts]

    monkeypatch.setattr("modules.embedding.encoder.embed", embed)
    monkeypatch.setattr("modules.embedding.encoder.missing_files", lambda *_: [])
    monkeypatch.setattr(
        "worker.ingestion.chunking._default_tokenizer", lambda: "character"
    )


@pytest.fixture
def studio_model(monkeypatch: pytest.MonkeyPatch) -> list[list[Source]]:
    """Stand in for Studio's model; yields what each call was grounded on."""
    selection = type(
        "Selection", (), {"provider": "fake", "name": "fake", "tier": Tier.COMPACT}
    )()
    monkeypatch.setattr(
        "worker.studio.job.resolve_routed_generation",
        lambda _session: ResolvedGeneration(selection, None),
    )
    seen: list[list[Source]] = []

    def fake(_model: object, _system: str, sources: list[Source], **_kw: object):
        seen.append(sources)
        return "# Probe\n\nBody."

    monkeypatch.setattr("worker.studio.shared.generate.run_model", fake)
    return seen


async def _upload(
    client: AsyncClient, workspace_id: int, folder_id: int, files: dict[str, str]
) -> list[dict]:
    """A dropped folder: each file with its path under the folder it was dropped on."""
    reply = await client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        data={
            "folder_id": str(folder_id),
            "relative_paths": json.dumps(list(files)),
        },
        files=[
            ("files", (path.rsplit("/", 1)[-1], content.encode(), "text/plain"))
            for path, content in files.items()
        ],
    )
    assert reply.status_code == 201, reply.text
    outcome = reply.json()
    assert outcome["duplicates"] == [] and outcome["rejected"] == []
    return outcome["created"]


async def _folder(
    client: AsyncClient, workspace_id: int, name: str, parent_id: int | None = None
) -> dict:
    reply = await client.post(
        f"/workspaces/{workspace_id}/folders",
        json={"name": name, "parent_id": parent_id},
    )
    assert reply.status_code == 201, reply.text
    return reply.json()


async def _cited(client: AsyncClient, thread_id: int, body: dict) -> set[int]:
    catalog: set[int] = set()
    async with client.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json=body
    ) as reply:
        assert reply.status_code == 200, await reply.aread()
        async for line in reply.aiter_lines():
            if line.startswith("data: {"):
                event = json.loads(line[len("data: ") :])
                if event["type"] == "citation-catalog":
                    catalog = {item["document_id"] for item in event["items"]}
    return catalog


async def test_a_ticked_folder_grounds_chat_and_studio_on_exactly_its_sources(
    client: AsyncClient,
    engine: Engine,
    stub_encoder: None,
    studio_model: list[list[Source]],
    llamacpp_server: list,
) -> None:
    """Sixty-two files under one folder, the answer in the oldest; the same
    answer outside the folder must never be read."""
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="llamacpp",
                name="Qwen3-1.7B-Q4_K_M",
            )
        )
        session.commit()
    workspace_id = (await client.post("/workspaces", json={"name": "Lab"})).json()["id"]
    research = await _folder(client, workspace_id, "Research")
    elsewhere = await _folder(client, workspace_id, "Elsewhere")

    # The answer first, so it is the oldest; one file sits a level deeper.
    inside = await _upload(
        client,
        workspace_id,
        research["id"],
        {
            "Probe/answer.txt": ANSWER,
            **{
                f"Probe/log-{n:02}.txt": f"Line {n} records a routine pump check."
                for n in range(FILLERS)
            },
            "Probe/deep/valve.txt": "The valve was replaced in spring.",
        },
    )
    outside = await _upload(
        client,
        workspace_id,
        elsewhere["id"],
        {"decoy.txt": f"Copied here too: {ANSWER}"},
    )
    for document in [*inside, *outside]:
        ingest(document["id"])

    folders = (await client.get(f"/workspaces/{workspace_id}/folders")).json()
    probe = next(f for f in folders if f["name"] == "Probe")
    assert probe["parent_id"] == research["id"]
    inside_ids = sorted(document["id"] for document in inside)
    answer_id = inside_ids[0]
    decoy_id = outside[0]["id"]
    scope = {"folder_ids": [probe["id"]]}
    # What an older client sent: the 50 newest ticked ids, the answer not among them.
    newest_fifty = inside_ids[-50:]

    counted = await client.post(
        f"/workspaces/{workspace_id}/source-scope/resolve", json=scope
    )
    assert counted.json()["counts"] == {
        "ready": FILLERS + 2,
        "indexing": 0,
        "failed": 0,
        "removed": 0,
    }

    # Chat: the scope wins over the id list sent beside it.
    thread = await client.post(f"/workspaces/{workspace_id}/chat/threads", json={})
    thread_id = thread.json()["id"]
    cited = await _cited(
        client,
        thread_id,
        {
            "text": "Which generator did the probe carry? RTGX7",
            "source_scope": scope,
            "document_ids": newest_fifty,
        },
    )
    assert answer_id in cited
    assert cited <= set(inside_ids)
    assert decoy_id not in cited
    turn = (await client.get(f"/chat/threads/{thread_id}/messages")).json()[0]
    assert turn["content"]["resolved"] == {
        "count": FILLERS + 2,
        "ids_sha256": hashlib.sha256(json.dumps(inside_ids).encode()).hexdigest(),
    }

    # Studio: the job records the whole folder, and the model reads all of it.
    job = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={
            "format": "summary",
            "source_scope": scope,
            "document_ids": newest_fifty,
        },
    )
    assert job.status_code == 201, job.text
    artifact_id = job.json()["id"]
    run_studio(artifact_id)

    with create_session_factory(engine)() as session:
        artifact = session.get(Artifact, artifact_id)
        assert artifact is not None
        metadata = artifact.artifact_metadata
    assert metadata["source_document_ids"] == inside_ids
    assert sorted(metadata["grounded_document_ids"]) == inside_ids
    assert sorted(source.document_id for source in studio_model[0]) == inside_ids
    assert any(ANSWER in source.content for source in studio_model[0])
