"""Integration: infographic create/revise through verification and persistence."""

from __future__ import annotations

import io
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from langchain.tools import ToolRuntime
from PIL import Image, ImageDraw
from sqlalchemy import func, select

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    load_artifact_for_revision as load_revision_tool,
    save_artifact as save_artifact_tool,
)
from app.artifacts import service
from app.artifacts.persistence import Artifact, ArtifactFile, ArtifactFileRole
from app.artifacts.verification import service as verify_service
from app.db import ChatVisibility, Document, NewChatThread
from tests.utils.fake_sandbox import FakeSandboxSession

from .test_service import MemoryBackend

SECRET = "test-secret"


def _runtime(thread_id: int) -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=None,
        config={"configurable": {"thread_id": f"{thread_id}::task:infographic"}},
        stream_writer=None,
        tool_call_id="infographic",
        store=None,
    )


def _infographic_png(label: str) -> bytes:
    image = Image.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 1120, 720), fill="#dbeafe", outline="#1d4ed8", width=8)
    draw.rectangle((160, 180, 520, 620), fill="#fef3c7")
    draw.rectangle((680, 180, 1040, 620), fill="#dcfce7")
    draw.text((120, 110), label, fill="black")
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def _provenance() -> dict[str, object]:
    return {
        "question_preset_id": "infographic.visual-style",
        "question_preset_version": 1,
        "requested_style_id": "kawaii",
        "resolved_style_id": "kawaii",
        "image_gen_model_id": 17,
        "provider_model": "provider/model",
        "width": 1200,
        "height": 800,
    }


async def test_infographic_create_and_revise_preserves_provenance_and_blob(
    db_session,
    db_workspace,
    db_user,
    monkeypatch,
):
    thread = NewChatThread(
        title="Infographic artifact chat",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        visibility=ChatVisibility.PRIVATE,
    )
    db_session.add(thread)
    await db_session.flush()

    backend = MemoryBackend()
    markdown_path = "/workspace/guide.md"
    primary_path = "/workspace/guide.png"
    first_markdown = "# Product guide\n\n## Research\nInterview five users."
    sandbox = FakeSandboxSession(
        {
            markdown_path: first_markdown.encode(),
            primary_path: _infographic_png("Product guide"),
        }
    )

    class Registry:
        async def get_session(self, _thread_id, _workspace_id):
            return sandbox

    async def get_registry():
        return Registry()

    @asynccontextmanager
    async def session_context():
        yield db_session

    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(save_artifact_tool, "get_registry", get_registry)
    monkeypatch.setattr(save_artifact_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(save_artifact_tool.app_config, "SECRET_KEY", SECRET)
    monkeypatch.setattr(load_revision_tool, "get_registry", get_registry)
    monkeypatch.setattr(load_revision_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(load_revision_tool, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(load_revision_tool.app_config, "SECRET_KEY", SECRET)
    monkeypatch.setattr(
        load_revision_tool,
        "uuid4",
        lambda: type("Uuid", (), {"hex": "infographic-revision"})(),
    )

    verified = await verify_service.verify_artifact(
        sandbox,
        primary_path,
        format="infographic",
        workspace_id=db_workspace.id,
        vision_llm=object(),
        markdown_path=markdown_path,
        provenance=_provenance(),
        secret_key=SECRET,
    )
    assert verified.verified

    save_tool = save_artifact_tool.create_save_artifact_tool(db_workspace.id)
    runtime = _runtime(thread.id)
    created_command = await save_tool.coroutine(
        title="Product guide",
        markdown_representation=first_markdown,
        path=primary_path,
        runtime=runtime,
    )
    created = json.loads(created_command.update["messages"][0].content)
    artifact_id = created["artifact_id"]
    first_blob_keys = set(backend.data)

    assert created["format"] == "infographic"
    artifact = await db_session.get(Artifact, artifact_id)
    assert artifact.artifact_metadata["generation"] == _provenance()

    load_tool = load_revision_tool.create_load_artifact_for_revision_tool(
        workspace_id=db_workspace.id
    )
    loaded = await load_tool.coroutine(artifact_id=artifact_id, runtime=runtime)
    revision_dir = (
        f"/workspace/artifact-revisions/{artifact_id}/infographic-revision"
    )
    assert loaded["primary_path"] == f"{revision_dir}/current.png"
    assert loaded["expected_output_path"] == f"{revision_dir}/revised.png"
    assert loaded["style_provenance"]["resolved_style_id"] == "kawaii"
    assert loaded["infographic_selection_token"]

    revised_markdown = "# Product guide\n\n## Research\nInterview ten users."
    sandbox.files[loaded["markdown_path"]] = revised_markdown.encode()
    sandbox.files[loaded["expected_output_path"]] = _infographic_png("Revised guide")
    revised_verified = await verify_service.verify_artifact(
        sandbox,
        loaded["expected_output_path"],
        format="infographic",
        workspace_id=db_workspace.id,
        vision_llm=object(),
        markdown_path=loaded["markdown_path"],
        provenance=_provenance(),
        secret_key=SECRET,
    )
    assert revised_verified.verified

    revised_command = await save_tool.coroutine(
        title="Product guide",
        markdown_representation=revised_markdown,
        path=loaded["expected_output_path"],
        artifact_id=artifact_id,
        expected_generation=loaded["expected_generation"],
        runtime=runtime,
    )
    revised = json.loads(revised_command.update["messages"][0].content)

    assert revised["generation"] == 2
    assert await db_session.scalar(
        select(func.count(Artifact.id)).where(Artifact.id == artifact_id)
    ) == 1
    assert await db_session.scalar(
        select(func.count(ArtifactFile.id)).where(
            ArtifactFile.artifact_id == artifact_id
        )
    ) == 1
    stored = (
        await db_session.scalars(
            select(ArtifactFile).where(ArtifactFile.artifact_id == artifact_id)
        )
    ).one()
    assert stored.role is ArtifactFileRole.PRIMARY
    assert stored.original_filename == "revised.png"
    document = await db_session.get(Document, artifact.document_id)
    assert document.source_markdown == revised_markdown
    assert len(backend.data) == 1
    assert set(backend.data).isdisjoint(first_blob_keys)
