"""A source or artifact named with `@` reaches the turn, whatever is ticked."""

import json

import pytest
from sqlalchemy import Engine

from modules.agent.agent_threads.mention_note import name_mentions, noted_mentions
from modules.agent.agent_threads.scope_note import NAMED_PATHS
from modules.agent.agent_threads.turn_sources import turn_sources
from modules.agent.tool_endpoint.turn_scope import thread_turn_scope
from modules.artifacts.models import Artifact
from modules.chat.schemas import MessageCreate, ThreadRead
from modules.documents.models import Document, DocumentType
from modules.folders.models import Folder
from modules.source_scope.mentioned import mentioned_of
from modules.source_scope.schemas import SourceScope
from shared.db import create_session_factory
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_threads import (
    ingest_note,
    open_thread,
    send,
    thread_folder,
)
from tests.integration.agent.test_turn_sources import (
    _agent_thread,
    _ready,
    _workspace_with_library,
)

pytestmark = pytest.mark.integration


def test_a_named_source_outside_the_ticks_joins_the_turn(engine: Engine) -> None:
    """The panel's ticks stand; the named file is added beside them."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        ticked = _ready(session, workspace_id, "Plan", library)
        named = _ready(session, workspace_id, "Memo", library)
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="Compare with @Memo",
                source_scope=SourceScope(document_ids=[ticked]),
                mentioned_sources={"document_ids": [named]},
            ),
        )

        assert sources.document_ids == [ticked, named]
        assert sources.mention_note is not None
        assert f"Memo [{named}].md" in sources.mention_note


def test_a_source_named_earlier_stays_in_the_threads_scope(engine: Engine) -> None:
    """A follow-up about it must not be refused, though each send replaces the ticks."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        ticked = _ready(session, workspace_id, "Plan", library)
        named = _ready(session, workspace_id, "Memo", library)
        thread = _agent_thread(session, workspace_id)
        ticks = SourceScope(document_ids=[ticked])
        turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Memo",
                source_scope=ticks,
                mentioned_sources={"document_ids": [named]},
            ),
        )

        follow_up = turn_sources(
            session, thread, MessageCreate(text="and page 3?", source_scope=ticks)
        )

        assert follow_up.document_ids == [ticked, named]
        assert thread_turn_scope(session, workspace_id, thread.id).document_ids == {
            ticked,
            named,
        }
        # Only the message that names it says so.
        assert follow_up.mention_note is None


def test_naming_a_source_overrides_unticking_it(engine: Engine) -> None:
    """An exclusion would otherwise come out last, whatever else names the file."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        unticked = _ready(session, workspace_id, "Memo", library)
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Memo",
                source_scope=SourceScope(all=True, excluded_document_ids=[unticked]),
                mentioned_sources={"document_ids": [unticked]},
            ),
        )

        assert sources.document_ids == [unticked]


def test_on_every_source_only_the_mention_note_says_which_file(engine: Engine) -> None:
    """A turn on every source sends no scope note, so nothing else could say."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        _ready(session, workspace_id, "Plan", library)
        named = _ready(session, workspace_id, "Memo", library)
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Memo",
                source_scope=SourceScope(all=True),
                mentioned_sources={"document_ids": [named]},
            ),
        )

        assert sources.note is None
        assert sources.mention_note is not None
        assert f"Memo [{named}].md" in sources.mention_note
        assert "Plan" not in sources.mention_note


def test_an_unfiled_artifact_can_be_named_and_is_given_its_artifact_id(
    engine: Engine,
) -> None:
    """Every source never takes an unfiled artifact; naming one does."""
    with create_session_factory(engine)() as session:
        workspace_id, _ = _workspace_with_library(session)
        document = _ready(session, workspace_id, "Draft", None, DocumentType.ARTIFACT)
        artifact = Artifact(
            document_id=document, workspace_id=workspace_id, format="docx"
        )
        session.add(artifact)
        session.flush()
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Draft",
                source_scope=SourceScope(all=True),
                mentioned_sources={"document_ids": [document]},
            ),
        )

        assert document in sources.document_ids
        assert sources.mention_note is not None
        assert f"(artifact {artifact.id})" in sources.mention_note


def test_a_named_folder_under_an_excluded_parent_gives_its_files(
    engine: Engine,
) -> None:
    """A folder in the scope alone would be taken back out by its parent's exclusion."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        root = session.get(Folder, library).root_id
        parent = Folder(
            workspace_id=workspace_id,
            root_id=root,
            parent_id=library,
            name="Work",
            name_key="work",
        )
        session.add(parent)
        session.flush()
        child = Folder(
            workspace_id=workspace_id,
            root_id=root,
            parent_id=parent.id,
            name="Q3",
            name_key="q3",
        )
        session.add(child)
        session.flush()
        inside = _ready(session, workspace_id, "Plan", child.id)
        _ready(session, workspace_id, "Other", parent.id)
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Q3",
                source_scope=SourceScope(all=True, excluded_folder_ids=[parent.id]),
                mentioned_sources={"folder_ids": [child.id]},
            ),
        )

        assert sources.document_ids == [inside]


def test_past_the_named_paths_the_note_counts_the_rest(engine: Engine) -> None:
    """Every turn's note stays in the session, so a large folder is not listed whole."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        named = [
            _ready(session, workspace_id, f"n{n}", library)
            for n in range(NAMED_PATHS + 3)
        ]
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="all of these",
                source_scope=SourceScope(),
                mentioned_sources={"document_ids": named},
            ),
        )

        assert sources.mention_note is not None
        assert sources.mention_note.count('"sources/') == NAMED_PATHS
        assert "and 3 more" in sources.mention_note


def test_a_named_source_deleted_since_drops_out(engine: Engine) -> None:
    """A deleted source is pruned as a ticked one is, rather than refused."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        named = _ready(session, workspace_id, "Memo", library)
        thread = _agent_thread(session, workspace_id)
        ticks = SourceScope()
        turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Memo",
                source_scope=ticks,
                mentioned_sources={"document_ids": [named]},
            ),
        )
        session.delete(session.get(Document, named))
        session.flush()

        sources = turn_sources(
            session, thread, MessageCreate(text="again", source_scope=ticks)
        )

        assert sources.document_ids == []
        assert mentioned_of(thread.source_scope) == []


def test_a_named_folder_and_artifact_keep_their_kind_in_the_tag(engine: Engine) -> None:
    """A chip needs what was named, not the files a folder gave."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        root = session.get(Folder, library).root_id
        folder = Folder(
            workspace_id=workspace_id,
            root_id=root,
            parent_id=library,
            name="Contracts",
            name_key="contracts",
        )
        session.add(folder)
        session.flush()
        _ready(session, workspace_id, "Plan", folder.id)
        document = _ready(session, workspace_id, "Deck", None, DocumentType.ARTIFACT)
        session.add(
            Artifact(document_id=document, workspace_id=workspace_id, format="pptx")
        )
        session.flush()
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Contracts @Deck",
                source_scope=SourceScope(),
                mentioned_sources={
                    "document_ids": [document],
                    "folder_ids": [folder.id],
                    "chips": [
                        {"id": f"folder:{folder.id}", "at": 0, "length": 10},
                        {"id": f"document:{document}", "at": 11, "length": 5},
                    ],
                },
            ),
        )
        turn = {
            "content": {
                "mentions": noted_mentions(
                    [{"type": "synthetic", "text": sources.mention_note}]
                )
            }
        }
        name_mentions(session, workspace_id, [turn])

        assert turn["content"]["mentions"] == [
            {
                "id": f"folder:{folder.id}",
                "type": "source",
                "label": "Contracts",
                "at": 0,
                "length": 10,
            },
            {
                "id": f"document:{document}",
                "type": "artifact-pptx",
                "label": "Deck",
                "at": 11,
                "length": 5,
            },
        ]


def test_a_thread_read_shows_its_ticks_alone(engine: Engine) -> None:
    """The API's scope refuses any other key, and the panel owns only the ticks."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        named = _ready(session, workspace_id, "Memo", library)
        thread = _agent_thread(session, workspace_id)
        turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Memo",
                source_scope=SourceScope(),
                mentioned_sources={"document_ids": [named]},
            ),
        )

        read = ThreadRead.model_validate(thread)

        assert read.source_scope == SourceScope()


async def test_opencode_can_read_and_search_a_named_source_that_is_not_ticked(
    agent_api: AgentAPI, engine: Engine, real_model: object
) -> None:
    """The file is mirrored, the tools take it, and the thread reads as the user wrote it."""
    ticked, _ = ingest_note(engine, agent_api.workspace_id, "Plan", "Ship on Friday.")
    named, chunk = ingest_note(
        engine, agent_api.workspace_id, "Memo", "Ship on Monday."
    )
    search = {"name": "surfsense_search_sources", "arguments": {"query": "ship"}}
    agent_api.model.replies = [("call", json.dumps(search)), ("text", "Monday.")]
    thread = await open_thread(agent_api)

    await send(
        agent_api,
        thread["id"],
        "When per @Memo?",
        source_scope={"document_ids": [ticked]},
        mentioned_sources={"document_ids": [named]},
    )

    folder = thread_folder(agent_api.workspace_id, thread["id"])
    assert (folder / "sources" / f"Memo [{named}].md").exists()
    asked, answered = agent_api.model.requests[:2]
    told = json.dumps([m for m in asked["messages"] if m["role"] == "user"])
    assert "The user named these sources" in told
    assert f"Memo [{named}].md" in told
    assert f"[{chunk}]" in json.dumps(
        [m for m in answered["messages"] if m["role"] == "tool"]
    )
    stored = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()
    assert stored[0]["content"]["text"] == "When per @Memo?"
    assert stored[0]["content"]["scope"]["document_ids"] == [ticked, named]


async def test_a_thread_reads_back_what_each_message_named(
    agent_api: AgentAPI, engine: Engine, real_model: object
) -> None:
    """The bubble's chips: named by what the source is called now, and a deleted one goes."""
    kept, _ = ingest_note(engine, agent_api.workspace_id, "Memo", "Ship on Monday.")
    deleted, _ = ingest_note(engine, agent_api.workspace_id, "Old", "Ship on Friday.")
    agent_api.model.replies = [("text", "Monday.")]
    thread = await open_thread(agent_api)
    await send(
        agent_api,
        thread["id"],
        "When per @Memo and @Old?",
        source_scope={"all": True},
        mentioned_sources={
            "document_ids": [kept, deleted],
            "chips": [
                {"id": f"document:{kept}", "at": 9, "length": 5},
                {"id": f"document:{deleted}", "at": 19, "length": 4},
            ],
        },
    )
    with create_session_factory(engine)() as session:
        session.delete(session.get(Document, deleted))
        session.commit()

    stored = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()

    assert stored[0]["content"]["text"] == "When per @Memo and @Old?"
    assert stored[0]["content"]["mentions"] == [
        {
            "id": f"document:{kept}",
            "type": "source",
            "label": "Memo",
            "at": 9,
            "length": 5,
        }
    ]


async def test_a_message_naming_nothing_reads_back_no_mentions(
    agent_api: AgentAPI, engine: Engine, real_model: object
) -> None:
    """A typed `[surfsense-mentions: ...]` is the user's words, not a note."""
    agent_api.model.replies = [("text", "Hi.")]
    thread = await open_thread(agent_api)
    typed = "[surfsense-mentions: document:1@0+5]"

    await send(agent_api, thread["id"], typed, source_scope={"all": True})

    stored = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()
    assert stored[0]["content"]["text"] == typed
    assert "mentions" not in stored[0]["content"]


def test_a_named_folder_with_nothing_ready_is_said(engine: Engine) -> None:
    """Told only "start from them", the agent would answer from what else is ticked."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        ticked = _ready(session, workspace_id, "Plan", library)
        empty = Folder(
            workspace_id=workspace_id,
            root_id=session.get(Folder, library).root_id,
            parent_id=library,
            name="Empty",
            name_key="empty",
        )
        session.add(empty)
        session.flush()
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Empty",
                source_scope=SourceScope(document_ids=[ticked]),
                mentioned_sources={"folder_ids": [empty.id]},
            ),
        )

        assert sources.mention_note is not None
        assert "Start from them" not in sources.mention_note
        assert "1 of what they named has nothing ready" in sources.mention_note


def test_a_named_folder_that_gave_nothing_is_said_beside_what_did(
    engine: Engine,
) -> None:
    """One empty folder must not pass unnoticed behind a file that was found."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        named = _ready(session, workspace_id, "Memo", library)
        empty = Folder(
            workspace_id=workspace_id,
            root_id=session.get(Folder, library).root_id,
            parent_id=library,
            name="Empty",
            name_key="empty",
        )
        session.add(empty)
        session.flush()
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="@Memo @Empty",
                source_scope=SourceScope(),
                mentioned_sources={
                    "document_ids": [named],
                    "folder_ids": [empty.id],
                },
            ),
        )

        assert sources.mention_note is not None
        assert f"Memo [{named}].md" in sources.mention_note
        assert "1 of what they named has nothing ready" in sources.mention_note


def test_readable_sources_are_listed_ahead_of_those_with_no_text(
    engine: Engine,
) -> None:
    """Sources with no text must not use up the note's paths."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        no_text = [
            _ready(session, workspace_id, f"n{n}", library) for n in range(NAMED_PATHS)
        ]
        for document in no_text:
            session.get(Document, document).content = None
        readable = _ready(session, workspace_id, "Memo", library)
        session.flush()
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(
                text="all of these",
                source_scope=SourceScope(),
                mentioned_sources={"document_ids": [*no_text, readable]},
            ),
        )

        assert sources.mention_note is not None
        assert f"Memo [{readable}].md" in sources.mention_note
        assert f"{NAMED_PATHS} more they named cannot be read" in sources.mention_note
