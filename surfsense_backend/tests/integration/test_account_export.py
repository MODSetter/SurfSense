"""Contract-3 producer: account ZIP from a real DB."""

from __future__ import annotations

import importlib.util
import json
import os
import zipfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Chunk,
    Document,
    DocumentStatus,
    DocumentType,
    Folder,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    User,
    Workspace,
)
from app.routes.workspaces_routes import create_default_roles_and_membership
from app.services.export_service import build_account_export_zip

pytestmark = pytest.mark.integration


def _contracts_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "plans" / "community-local" / "contracts"
        if candidate.is_dir():
            return candidate
    raise RuntimeError("plans/community-local/contracts not found")


def _check_export_sample(root: Path) -> int:
    spec = importlib.util.spec_from_file_location(
        "check_export_sample", _contracts_dir() / "check-export-sample.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main(root)


async def _add_doc(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    title: str,
    folder_id: int | None,
    uid: str,
    document_type: DocumentType = DocumentType.FILE,
    status: dict | None = None,
    markdown: str | None = "# Body\n",
) -> Document:
    doc = Document(
        title=title,
        document_type=document_type,
        document_metadata={},
        content=markdown or "",
        content_hash=uid,
        unique_identifier_hash=uid,
        source_markdown=markdown,
        workspace_id=workspace.id,
        created_by_id=user.id,
        folder_id=folder_id,
        status=status if status is not None else DocumentStatus.ready(),
    )
    session.add(doc)
    await session.flush()
    return doc


async def test_account_export_matches_contract_and_skips_pending(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace, tmp_path: Path
):
    research = Folder(name="Research", position="0", workspace_id=db_workspace.id)
    db_session.add(research)
    await db_session.flush()
    ai = Folder(
        name="AI",
        position="0",
        workspace_id=db_workspace.id,
        parent_id=research.id,
    )
    db_session.add(ai)
    await db_session.flush()

    notes = await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Notes",
        folder_id=ai.id,
        uid="acct-notes",
        document_type=DocumentType.FILE,
    )
    await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Notes",
        folder_id=ai.id,
        uid="acct-notes-2",
        document_type=DocumentType.NOTE,
    )
    await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="index",
        folder_id=research.id,
        uid="acct-index",
        document_type=DocumentType.NOTION_CONNECTOR,
    )
    await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Résumé de réunion",
        folder_id=None,
        uid="acct-unicode",
        document_type=DocumentType.SLACK_CONNECTOR,
    )
    pending = await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Draft",
        folder_id=None,
        uid="acct-pending",
        status=DocumentStatus.processing(),
        markdown="# still cooking",
    )

    empty = Workspace(name="Empty", user_id=db_user.id)
    db_session.add(empty)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, empty.id, db_user.id)

    cited = await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Alpha",
        folder_id=None,
        uid="acct-alpha",
        document_type=DocumentType.FILE,
    )
    beta = await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Beta",
        folder_id=None,
        uid="acct-beta",
        document_type=DocumentType.FILE,
    )
    gamma = await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Gamma",
        folder_id=None,
        uid="acct-gamma",
        document_type=DocumentType.FILE,
    )
    chunks = []
    for source_doc in (cited, beta, gamma):
        chunk = Chunk(content="passage", document_id=source_doc.id, position=0)
        db_session.add(chunk)
        chunks.append(chunk)
    await db_session.flush()

    thread = NewChatThread(
        title="Citations",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(thread)
    await db_session.flush()
    db_session.add(
        NewChatMessage(
            thread_id=thread.id,
            role=NewChatMessageRole.USER,
            content=[{"type": "text", "text": "compare these"}],
            author_id=db_user.id,
        )
    )
    marker_text = (
        f"See [citation:{chunks[0].id}] then "
        f"[citation:{chunks[1].id}] and [citation:{chunks[2].id}]."
    )
    db_session.add(
        NewChatMessage(
            thread_id=thread.id,
            role=NewChatMessageRole.ASSISTANT,
            content=[{"type": "text", "text": marker_text}],
            author_id=db_user.id,
        )
    )
    db_session.add(
        NewChatMessage(
            thread_id=thread.id,
            role=NewChatMessageRole.SYSTEM,
            content=[{"type": "text", "text": "ignored"}],
            author_id=db_user.id,
        )
    )
    await db_session.flush()

    result = await build_account_export_zip(db_session, db_user.id)
    try:
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
            assert names[0] == "manifest.json"
            zf.extractall(tmp_path)
    finally:
        os.unlink(result.zip_path)

    assert _check_export_sample(tmp_path) == 0

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == "surfsense-export/1"
    by_id = {ws["id"]: ws for ws in manifest["workspaces"]}
    assert set(by_id) == {db_workspace.id, empty.id}

    research_ws = by_id[db_workspace.id]
    listed_ids = {doc["id"] for doc in research_ws["documents"]}
    assert pending.id not in listed_ids
    assert {"id": pending.id, "title": "Draft", "reason": "processing"} in research_ws[
        "skipped"
    ]
    paths = {doc["path"] for doc in research_ws["documents"]}
    assert any(path.endswith("Notes.md") and "Notes_2.md" not in path for path in paths)
    assert any(path.endswith("Notes_2.md") for path in paths)
    assert any(path.endswith("index_.md") for path in paths)
    assert any("Résumé de réunion.md" in path for path in paths)
    assert notes.id in listed_ids

    empty_ws = by_id[empty.id]
    assert empty_ws["documents"] == []
    assert empty_ws["skipped"] == []
    assert empty_ws["chats"] == f"workspaces/{empty.id}/chats.json"
    assert json.loads((tmp_path / empty_ws["chats"]).read_text(encoding="utf-8")) == []

    chats = json.loads((tmp_path / research_ws["chats"]).read_text(encoding="utf-8"))
    assert len(chats) == 1
    assistant = chats[0]["messages"][1]
    assert assistant["role"] == "assistant"
    assert "[citation:" not in assistant["text"]
    assert assistant["citations"] == [
        {"title": "Alpha"},
        {"title": "Beta"},
        {"title": "Gamma"},
    ]
    assert all(msg["role"] in {"user", "assistant"} for msg in chats[0]["messages"])
