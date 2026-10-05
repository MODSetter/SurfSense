"""SurfSense's tools keep to the sources ticked for the turn that calls them."""

import pytest
from sqlalchemy import Engine

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.folders.models import Folder
from modules.source_roots.managed_root import ensure_managed_root
from modules.source_scope.schemas import SourceScope
from shared.db import create_session_factory
from tests.integration.agent.test_document_tools import (
    LOGO,
    _artifact_id,
    _logo_source,
    _report_source,
    render,
)
from tests.integration.agent.test_office_documents import (
    DECK_FROM_TEMPLATE,
    _brand_deck,
    _letterhead,
    _uploaded,
)
from tests.integration.agent.test_office_documents import render as render_deck
from tests.integration.agent.test_tool_endpoint import (
    choose_chat_model,
    ingest,
    ready_note,
)
from tests.integration.agent.tool_endpoint_client import ToolEndpoint
from tests.integration.worker.conftest import stub_model  # noqa: F401

pytestmark = pytest.mark.integration

SEARCH = {"query": "When do we ship?"}


async def test_a_search_finds_only_the_ticked_sources(
    tools: ToolEndpoint, engine: Engine, real_model: object
) -> None:
    """An unticked source's passage would reach the answer however the model is told."""
    workspace_id = await tools.workspace()
    ticked, ticked_chunk = ingest(engine, workspace_id, "Plan", "We ship on Friday.")
    _, unticked_chunk = ingest(engine, workspace_id, "Memo", "We ship on Monday.")

    text, is_error = await tools.call(
        workspace_id,
        "search_sources",
        SEARCH,
        thread=tools.thread(workspace_id, SourceScope(document_ids=[ticked])),
    )

    assert is_error is False, text
    assert f'cite="[{ticked_chunk}]"' in text
    assert f'cite="[{unticked_chunk}]"' not in text


async def test_a_passage_is_labelled_with_its_file_in_the_users_folders(
    tools: ToolEndpoint, engine: Engine, real_model: object
) -> None:
    """The label is the path the agent opens it at in its own folder."""
    workspace_id = await tools.workspace()
    ticked, _ = ingest(engine, workspace_id, "Plan", "We ship on Friday.")
    with create_session_factory(engine)() as session:
        library = ensure_managed_root(session, workspace_id)
        research = Folder(
            workspace_id=workspace_id,
            root_id=library.root_id,
            parent_id=library.id,
            name="Research",
            name_key="research",
        )
        session.add(research)
        session.flush()
        session.get(Document, ticked).folder_id = research.id
        session.commit()
        research_id = research.id

    text, is_error = await tools.call(
        workspace_id,
        "search_sources",
        SEARCH,
        thread=tools.thread(workspace_id, SourceScope(folder_ids=[research_id])),
    )

    assert is_error is False, text
    assert f'source="sources/Library/Research/Plan [{ticked}].md"' in text


async def test_with_nothing_ticked_a_search_finds_nothing_and_says_why(
    tools: ToolEndpoint, engine: Engine, real_model: object
) -> None:
    """An empty selection is no sources, as a chat message's empty list is."""
    workspace_id = await tools.workspace()
    _, chunk = ingest(engine, workspace_id, "Plan", "We ship on Friday.")

    text, _ = await tools.call(
        workspace_id,
        "search_sources",
        SEARCH,
        thread=tools.thread(workspace_id, SourceScope()),
    )

    assert f"[{chunk}]" not in text
    assert "No sources are selected" in text


async def test_a_search_that_finds_nothing_points_only_at_the_ticked_files(
    tools: ToolEndpoint, engine: Engine, real_model: object
) -> None:
    """Pointed at all of sources/, the model would grep the unticked files next."""
    workspace_id = await tools.workspace()
    ingest(engine, workspace_id, "Memo", "We ship on Monday.")
    # Ready, so it has a file, but never indexed, so a search finds nothing in it.
    ticked = ready_note(engine, workspace_id)

    text, _ = await tools.call(
        workspace_id,
        "search_sources",
        SEARCH,
        thread=tools.thread(workspace_id, SourceScope(document_ids=[ticked])),
    )

    assert "No passage matched" in text
    assert "grep the files in sources/" not in text
    assert "selected sources' files" in text


@pytest.mark.parametrize("caller", ["no such thread", "a chat thread", "elsewhere"])
async def test_a_call_from_no_agent_thread_of_the_workspace_is_refused_not_widened(
    tools: ToolEndpoint, engine: Engine, real_model: object, caller: str
) -> None:
    """Without its thread's scope a tool cannot tell which sources it may read."""
    workspace_id, elsewhere = await tools.workspace(), await tools.workspace()
    _, chunk = ingest(engine, workspace_id, "Plan", "We ship on Friday.")
    report = _report_source(engine, workspace_id)
    thread = {
        "no such thread": 999_999,
        "a chat thread": tools.thread(workspace_id, agent=False),
        "elsewhere": tools.thread(elsewhere),
    }[caller]

    searched, search_refused = await tools.call(
        workspace_id, "search_sources", SEARCH, thread=thread
    )
    listed, list_refused = await tools.call(
        workspace_id, "list_images", {"source_ids": [report]}, thread=thread
    )

    assert (search_refused, list_refused) == (True, True)
    assert f"[{chunk}]" not in searched
    assert f"{report}-1" not in listed
    assert "send the message again" in searched


async def test_the_address_without_a_thread_is_gone(tools: ToolEndpoint) -> None:
    """Every thread registers its own address; a workspace-wide one would serve any turn."""
    workspace_id = await tools.workspace()

    reply = await tools.client.post(
        f"/agent/tools/workspaces/{workspace_id}",
        params={"scope": "anything"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Authorization": f"Bearer {tools.launch_key}"},
    )

    assert reply.status_code == 404


async def test_a_call_follows_ticks_stored_since_the_turn_began(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """The thread's stored scope is read on every call, not kept from the turn."""
    workspace_id = await tools.workspace()
    first = _report_source(engine, workspace_id)
    second = _report_source(engine, workspace_id)
    thread = tools.thread(workspace_id, SourceScope(document_ids=[first]))
    stored = await tools.client.put(
        f"/chat/threads/{thread}/source-scope", json={"document_ids": [second]}
    )
    assert stored.status_code == 200, stored.text

    refused, is_error = await tools.call(
        workspace_id, "list_images", {"source_ids": [first]}, thread=thread
    )
    listed, _ = await tools.call(
        workspace_id, "list_images", {"source_ids": [second]}, thread=thread
    )

    assert is_error is True and f"Source {first} is not selected" in refused
    assert f"{second}-1" in listed


async def test_every_source_still_means_only_what_the_scope_resolves_to(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """A thread that ticked everything is held to its ready sources too."""
    workspace_id = await tools.workspace()
    pending = ready_note(engine, workspace_id)
    with create_session_factory(engine)() as session:
        session.get(Document, pending).status = DocumentStatus.PENDING
        session.commit()

    text, is_error = await tools.call(
        workspace_id, "list_images", {"source_ids": [pending]}
    )

    assert is_error is True
    assert f"Source {pending} is not selected" in text


async def test_a_refusal_in_a_wide_scope_names_a_few_ids_not_all(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """Every id of 5,000 would put 30 KB in front of the model on each refusal."""
    workspace_id = await tools.workspace()
    with create_session_factory(engine)() as session:
        session.add_all(
            Document(
                workspace_id=workspace_id,
                title=f"n{n}",
                document_type=DocumentType.NOTE,
                status=DocumentStatus.READY,
                content="x",
            )
            for n in range(5000)
        )
        session.commit()
    theirs = ready_note(engine, await tools.workspace())

    text, is_error = await tools.call(
        workspace_id, "list_images", {"source_ids": [theirs]}
    )

    assert is_error is True
    assert len(text) < 1000
    assert "and 4980 more" in text and "sources/" in text


async def test_listing_images_of_an_unticked_source_is_refused(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """The refusal names what is ticked, so the model can carry on or ask."""
    workspace_id = await tools.workspace()
    ticked = _report_source(engine, workspace_id)
    unticked = _report_source(engine, workspace_id)

    text, is_error = await tools.call(
        workspace_id,
        "list_images",
        {"source_ids": [ticked, unticked]},
        thread=tools.thread(workspace_id, SourceScope(document_ids=[ticked])),
    )

    assert is_error is True
    assert f"{unticked}-1" not in text and f"{ticked}-1" not in text
    assert f"Source {unticked} is not selected" in text
    assert f"selected: {ticked}" in text


async def test_starting_studio_from_an_unticked_source_is_refused(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """Studio reads the sources it is given, so the scope is checked before it starts."""
    workspace_id = await tools.workspace()
    ticked, unticked = (
        ready_note(engine, workspace_id),
        ready_note(engine, workspace_id),
    )
    choose_chat_model(engine)

    text, is_error = await tools.call(
        workspace_id,
        "create_artifact",
        {"format": "quiz", "source_ids": [unticked]},
        thread=tools.thread(workspace_id, SourceScope(document_ids=[ticked])),
    )

    assert is_error is True
    assert f"Source {unticked} is not selected" in text
    listed = (await tools.client.get(f"/workspaces/{workspace_id}/artifacts")).json()
    assert listed == []


async def test_a_render_cannot_place_an_unticked_sources_image(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """An image is a source's content as much as its text is."""
    workspace_id = await tools.workspace()
    ticked = _logo_source(engine, workspace_id)
    unticked = _logo_source(engine, workspace_id)
    name = f"{unticked}-1"

    text, is_error = await tools.call(
        workspace_id,
        "render_document",
        render(script=LOGO.format(name=name), images=[name]),
        thread=tools.thread(workspace_id, SourceScope(document_ids=[ticked])),
    )

    assert is_error is True
    assert f'"{name}"' in text and "not selected" in text
    assert (
        await tools.client.get(f"/workspaces/{workspace_id}/artifacts")
    ).json() == []


@pytest.mark.usefixtures("stub_model")
async def test_the_agents_own_documents_stay_usable_whatever_is_ticked(
    tools: ToolEndpoint, studio_worker: None
) -> None:
    """A document the agent made is its output, not a source the user ticks."""
    workspace_id = await tools.workspace()
    nothing = tools.thread(workspace_id, SourceScope())
    first, _ = await tools.call(workspace_id, "render_document", render())

    script, read_refused = await tools.call(
        workspace_id,
        "read_document",
        {"artifact_id": _artifact_id(first)},
        thread=nothing,
    )
    second, render_refused = await tools.call(
        workspace_id,
        "render_document",
        render(artifact_id=_artifact_id(first)),
        thread=nothing,
    )

    assert (read_refused, render_refused) == (False, False), (script, second)
    assert ", version 2:" in second


async def test_a_render_cannot_start_from_an_unticked_sources_template(
    tools: ToolEndpoint, engine: Engine
) -> None:
    """A template is a source's content: its look, and whatever it holds."""
    workspace_id = await tools.workspace()
    ticked = _uploaded(engine, workspace_id, "Plan.docx", _letterhead())
    unticked = _uploaded(engine, workspace_id, "Brand.pptx", _brand_deck())

    text, is_error = await tools.call(
        workspace_id,
        "render_document",
        render_deck(script=DECK_FROM_TEMPLATE, template_source_id=unticked),
        thread=tools.thread(workspace_id, SourceScope(document_ids=[ticked])),
    )

    assert is_error is True
    assert f"Source {unticked} is not selected" in text
    assert f"selected: {ticked}" in text
    assert (
        await tools.client.get(f"/workspaces/{workspace_id}/artifacts")
    ).json() == []


@pytest.mark.usefixtures("stub_model")
async def test_a_next_version_cannot_keep_a_template_the_turn_no_longer_ticks(
    tools: ToolEndpoint, engine: Engine, studio_worker: None
) -> None:
    """Leaving the template out keeps it, so the kept one is held to the turn's sources too."""
    workspace_id = await tools.workspace()
    brand = _uploaded(engine, workspace_id, "Brand.pptx", _brand_deck())
    first, is_error = await tools.call(
        workspace_id,
        "render_document",
        render_deck(script=DECK_FROM_TEMPLATE, template_source_id=brand),
    )
    assert is_error is False, first

    text, is_error = await tools.call(
        workspace_id,
        "render_document",
        render_deck(script=DECK_FROM_TEMPLATE, artifact_id=_artifact_id(first)),
        thread=tools.thread(workspace_id, SourceScope()),
    )

    assert is_error is True
    assert f"starts from template source {brand}, which is not selected" in text
    assert "ask them to select" in text
