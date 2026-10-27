"""`GET /usage-statistics/summary` over a real migrated library.

The machine is stated, not probed: which card a test host has is not what these
tests are about. The database and the counts file are the real ones.
"""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from modules.artifacts.models import Artifact
from modules.chat.models import AgentEngineKind, ChatMessage, ChatThread, MessageRole
from modules.documents.models import Document, DocumentType
from modules.llm.hardware import Device, DeviceType, GpuStatus, SystemInventory
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.usage_statistics.activity_counts import (
    Activity,
    begin_counting,
    read_counts,
)
from modules.usage_statistics.activity_counts.counts_file import add, start_counting
from modules.usage_statistics.dependencies import (
    MachineReadings,
    get_machine_readings,
)
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

GIB = 1024**3
NOW = datetime.now(UTC)
WEEK_AGO = NOW - timedelta(days=7)
MACHINE = MachineReadings(
    inventory=lambda: SystemInventory(
        devices=(
            Device("Vulkan0", "NVIDIA GeForce RTX 3060", DeviceType.GPU, 12 * GIB, 0),
            Device("CPU", "Ryzen 5", DeviceType.CPU, 32 * GIB, 0),
        ),
        gpu_status=GpuStatus.PRESENT,
    ),
    os_adapter_names=lambda: ("NVIDIA GeForce RTX 3060", "AMD Radeon(TM) Graphics"),
    ram_total_bytes=lambda: int(31.2 * GIB),
    holds_local_model=lambda name: name == "Qwen3-4B-Q4_K_M",
    ui_language=lambda: "ja",
)


@pytest.fixture
def machine() -> MachineReadings:
    """The machine a test runs on, unless it parametrizes another."""
    return MACHINE


@pytest.fixture
async def client(
    engine: Engine, machine: MachineReadings
) -> AsyncIterator[AsyncClient]:
    """The app over this test's library, on the stated machine."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    app.dependency_overrides[get_machine_readings] = lambda: machine
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def summary(client: AsyncClient, since: datetime = WEEK_AGO) -> dict:
    """The summary for the week before now, which the weekly report asks for."""
    response = await client.get(
        "/usage-statistics/summary", params={"since": since.isoformat()}
    )
    assert response.status_code == 200, response.text
    return response.json()


def seed(
    engine: Engine,
    *,
    notes: int = 0,
    chat_turns: int = 0,
    model: str | None = None,
    answered: bool = False,
    artifacts: int = 0,
    old_turns: int = 0,
) -> None:
    """A library as a user leaves it: notes, Basic chat turns, Studio outputs, a model."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="w")
        session.add(workspace)
        session.flush()
        documents = [
            Document(
                workspace_id=workspace.id,
                title=f"n{i}",
                document_type=DocumentType.NOTE,
            )
            for i in range(notes)
        ]
        session.add_all(documents)
        chat = ChatThread(workspace_id=workspace.id, title="chat")
        agent = ChatThread(
            workspace_id=workspace.id,
            title="agent",
            agent_engine=AgentEngineKind.OPENCODE,
        )
        session.add_all([chat, agent])
        session.flush()
        for _ in range(chat_turns):
            session.add(
                ChatMessage(
                    chat_thread_id=chat.id, role=MessageRole.USER, content={"text": "q"}
                )
            )
        for _ in range(old_turns):
            session.add(
                ChatMessage(
                    chat_thread_id=chat.id,
                    role=MessageRole.USER,
                    content={"text": "q"},
                    created_at=(NOW - timedelta(days=30)).replace(tzinfo=None),
                )
            )
        if answered:
            session.add(
                ChatMessage(
                    chat_thread_id=chat.id,
                    role=MessageRole.ASSISTANT,
                    content={"text": "an answer", "citations": []},
                    completed_at=NOW,
                )
            )
        for i in range(artifacts):
            made = Document(
                workspace_id=workspace.id,
                title=f"a{i}",
                document_type=DocumentType.ARTIFACT,
            )
            session.add(made)
            session.flush()
            session.add(
                Artifact(document_id=made.id, workspace_id=workspace.id, format="docx")
            )
        if model is not None:
            session.add(
                SelectedModel(
                    model_type=ModelType.TEXT_GEN, provider="llamacpp", name=model
                )
            )
        session.commit()


async def test_a_new_install_reports_nothing_done_and_its_machine(
    client: AsyncClient,
) -> None:
    """Counting began before anything happened, so every zero is a real zero."""
    start_counting(had_chats=False)

    body = await summary(client)

    assert body == {
        "week": {
            "chat_turns": "0",
            "agent_turns": "0",
            "model_source": "none",
            "sources": "0",
            "studio_outputs": "0",
            "plugin_calls": "0",
            "onboarding": "not_started",
        },
        "hardware": {
            "ram_gb": "32-63",
            "gpu": "nvidia",
            "vram_gb": "12-23",
            "gpu_runtime": "reachable",
        },
        "ui_language": "ja",
    }


@pytest.mark.parametrize(
    "machine",
    [
        replace(
            MACHINE,
            inventory=lambda: SystemInventory(
                devices=(), gpu_status=GpuStatus.BROKEN_INSTALL
            ),
        )
    ],
)
async def test_a_card_the_runtime_cannot_reach_is_named_by_the_os(
    client: AsyncClient,
) -> None:
    """ggml listed nothing, so the maker comes from the OS and nothing sizes the card."""
    hardware = (await summary(client))["hardware"]

    assert hardware == {
        "ram_gb": "32-63",
        "gpu": "nvidia",
        "vram_gb": "unknown",
        "gpu_runtime": "unreachable",
    }


async def test_a_busy_week_is_reported_in_buckets(
    client: AsyncClient, engine: Engine
) -> None:
    """Basic chat from its rows, agent turns and plugin calls from the counts, Studio from its rows."""
    start_counting(had_chats=False)
    seed(
        engine,
        notes=12,
        chat_turns=11,
        old_turns=40,
        model="Qwen3-4B-Q4_K_M",
        answered=True,
        artifacts=2,
    )
    add({Activity.AGENT_TURN: 3, Activity.LOCAL_ANSWER: 14, Activity.PLUGIN_CALL: 12})
    add({Activity.REMOTE_ANSWER: 1}, now=NOW - timedelta(days=9))

    week = (await summary(client))["week"]

    assert week == {
        "chat_turns": "10-49",
        "agent_turns": "1-9",
        "model_source": "local",
        "sources": "10-99",
        "studio_outputs": "1-4",
        "plugin_calls": "10+",
        "onboarding": "first_answer",
    }


async def test_a_window_that_began_before_counting_is_unknown_not_zero(
    client: AsyncClient, engine: Engine
) -> None:
    """An updated install's agent turns before this release were never counted: never guessed."""
    seed(engine, chat_turns=2, model="Qwen3-4B-Q4_K_M")
    start_counting(had_chats=True)

    week = (await summary(client))["week"]

    assert (week["agent_turns"], week["model_source"], week["plugin_calls"]) == (
        "unknown",
        "unknown",
        "unknown",
    )
    assert week["chat_turns"] == "1-9"


async def test_no_counts_file_leaves_only_the_database_facts(
    client: AsyncClient,
) -> None:
    """Without the file nothing the file holds can be said."""
    week = (await summary(client))["week"]

    assert week["agent_turns"] == "unknown"
    assert week["chat_turns"] == "0"


@pytest.mark.parametrize(
    ("model", "notes", "step"),
    [
        (None, 0, "not_started"),
        ("Qwen3-1.7B-Q4_K_M", 0, "model_chosen"),
        ("Qwen3-4B-Q4_K_M", 0, "model_ready"),
        ("Qwen3-4B-Q4_K_M", 1, "first_source"),
    ],
)
async def test_onboarding_is_the_furthest_step_the_library_shows(
    client: AsyncClient, engine: Engine, model: str | None, notes: int, step: str
) -> None:
    """A chosen local model is ready once its file is here; a note is the first source."""
    seed(engine, model=model, notes=notes)

    assert (await summary(client))["week"]["onboarding"] == step


async def test_an_agent_answer_counts_as_an_answer_for_onboarding(
    client: AsyncClient, engine: Engine
) -> None:
    """An agent thread's turns live in its engine, so the counts vouch for them."""
    start_counting(had_chats=False)
    seed(engine, model="Qwen3-4B-Q4_K_M")
    add({Activity.AGENT_TURN: 1, Activity.REMOTE_ANSWER: 1})

    week = (await summary(client))["week"]

    assert (week["onboarding"], week["model_source"]) == ("first_answer", "remote")


async def test_an_agent_turn_that_never_answered_is_not_a_first_answer(
    client: AsyncClient, engine: Engine
) -> None:
    """A turn whose model failed counts as a turn, never as setup's last step."""
    start_counting(had_chats=False)
    seed(engine, model="Qwen3-4B-Q4_K_M")
    add({Activity.AGENT_TURN: 1})

    week = (await summary(client))["week"]

    assert (week["agent_turns"], week["model_source"]) == ("1-9", "none")
    assert week["onboarding"] == "model_ready"


@pytest.mark.parametrize("since", ["", "yesterday", "2026-13-40T00:00:00Z"])
async def test_a_missing_or_malformed_since_is_refused(
    client: AsyncClient, since: str
) -> None:
    """The window is the caller's to state; nothing is assumed."""
    params = {"since": since} if since else {}

    response = await client.get("/usage-statistics/summary", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(("chat_turns", "covered"), [(0, True), (3, False)])
def test_startup_counting_begins_whole_only_for_a_library_without_chats(
    engine: Engine, chat_turns: int, covered: bool
) -> None:
    """The API starts counting at boot; chats already there were never counted."""
    if chat_turns:
        seed(engine, chat_turns=chat_turns)

    with create_session_factory(engine)() as session:
        begin_counting(session)

    counts = read_counts()
    assert counts is not None
    assert counts.covers(WEEK_AGO) is covered
