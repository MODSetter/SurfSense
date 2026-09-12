from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    sandbox as sandbox_tools,
)
from app.artifacts.infographic.generation import GeneratedInfographic
from app.artifacts.infographic.presets import QUESTION_PRESET_ID, resolve_visual_style
from app.artifacts.infographic.selection import (
    issue_selection_token,
    read_generation_state,
)
from tests.utils.fake_sandbox import FakeSandboxSession


@asynccontextmanager
async def _db_session():
    yield object()


async def test_generation_writes_png_markdown_and_enforces_one_repair(
    monkeypatch,
) -> None:
    session = FakeSandboxSession()
    resolved = resolve_visual_style("sketch-note", "")
    token = issue_selection_token(
        workspace_id=7,
        thread_id=11,
        preset_id=QUESTION_PRESET_ID,
        preset_version=1,
        resolved=resolved,
        secret_key="secret",
    )
    generated = GeneratedInfographic(
        png=b"\x89PNG\r\n\x1a\nimage",
        width=1200,
        height=800,
        image_gen_model_id=17,
        provider_model="provider/model",
    )
    calls: list[tuple[str, ...]] = []

    async def fake_generate(_session, **kwargs):
        calls.append(tuple(kwargs["repair_findings"]))
        return generated

    monkeypatch.setattr(sandbox_tools.app_config, "SECRET_KEY", "secret")
    monkeypatch.setattr(sandbox_tools, "shielded_async_session", _db_session)
    monkeypatch.setattr(sandbox_tools, "generate_infographic", fake_generate)

    first = json.loads(
        await sandbox_tools._generate_infographic_file(
            session=session,
            workspace_id=7,
            thread_id=11,
            factual_markdown="# Guide\n\n## One\nFirst.",
            output_path="/workspace/guide.png",
            selection_token=token,
            output_constraints="4:3",
            repair_findings=None,
        )
    )
    assert first["attempt"] == 1
    assert session.files["/workspace/guide.png"] == generated.png
    assert session.files["/workspace/guide.md"] == b"# Guide\n\n## One\nFirst."

    second = json.loads(
        await sandbox_tools._generate_infographic_file(
            session=session,
            workspace_id=7,
            thread_id=11,
            factual_markdown="# Guide\n\n## One\nFirst.",
            output_path="/workspace/guide.png",
            selection_token=token,
            output_constraints="4:3",
            repair_findings=["The heading is clipped."],
        )
    )
    assert second["attempt"] == 2
    assert calls == [(), ("The heading is clipped.",)]

    with pytest.raises(ValueError, match="only one repair"):
        await sandbox_tools._generate_infographic_file(
            session=session,
            workspace_id=7,
            thread_id=11,
            factual_markdown="# Guide\n\n## One\nFirst.",
            output_path="/workspace/guide.png",
            selection_token=token,
            output_constraints="4:3",
            repair_findings=["Still clipped."],
        )

    state = await read_generation_state(
        session,
        "/workspace/guide.png",
        workspace_id=7,
        secret_key="secret",
    )
    assert state is not None
    assert state.attempts == 2
    assert state.manifest_provenance()["resolved_style_id"] == "sketch-note"


async def test_generation_rejects_untrusted_or_outside_paths(monkeypatch) -> None:
    monkeypatch.setattr(sandbox_tools.app_config, "SECRET_KEY", "secret")
    session = FakeSandboxSession()

    with pytest.raises(ValueError, match="under /workspace"):
        await sandbox_tools._generate_infographic_file(
            session=session,
            workspace_id=7,
            thread_id=11,
            factual_markdown="# Guide\n\n## One\nFirst.",
            output_path="/tmp/guide.png",
            selection_token="invalid",
            output_constraints=None,
            repair_findings=None,
        )
