"""SurfSense's tools keep to the sources ticked for the turn that calls them."""

import pytest
from sqlalchemy import Engine

from modules.agent.tool_endpoint.turn_scope import remember_turn_scope
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
        token=remember_turn_scope(workspace_id, [ticked]),
    )

    assert is_error is False, text
    assert f'cite="[{ticked_chunk}]"' in text
    assert f'cite="[{unticked_chunk}]"' not in text


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
        token=remember_turn_scope(workspace_id, []),
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
        token=remember_turn_scope(workspace_id, [ticked]),
    )

    assert "No passage matched" in text
    assert "grep the files in sources/" not in text
    assert "selected sources' files" in text


@pytest.mark.parametrize("token", [None, "made-up"])
async def test_a_call_from_no_known_turn_is_refused_not_widened(
    tools: ToolEndpoint, engine: Engine, real_model: object, token: str | None
) -> None:
    """Without its turn's scope a tool cannot tell which sources it may read."""
    workspace_id = await tools.workspace()
    _, chunk = ingest(engine, workspace_id, "Plan", "We ship on Friday.")
    report = _report_source(engine, workspace_id)

    searched, search_refused = await tools.call(
        workspace_id, "search_sources", SEARCH, token=token
    )
    listed, list_refused = await tools.call(
        workspace_id, "list_images", {"source_ids": [report]}, token=token
    )

    assert (search_refused, list_refused) == (True, True)
    assert f"[{chunk}]" not in searched
    assert f"{report}-1" not in listed
    assert "send the message again" in searched


async def test_another_workspaces_turn_cannot_lend_its_scope(
    tools: ToolEndpoint, engine: Engine, real_model: object
) -> None:
    """A token names the workspace it was made for."""
    workspace_id, elsewhere = await tools.workspace(), await tools.workspace()
    ingest(engine, workspace_id, "Plan", "We ship on Friday.")

    _, is_error = await tools.call(
        workspace_id,
        "search_sources",
        SEARCH,
        token=remember_turn_scope(elsewhere, None),
    )

    assert is_error is True


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
        token=remember_turn_scope(workspace_id, [ticked]),
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
        token=remember_turn_scope(workspace_id, [ticked]),
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
        token=remember_turn_scope(workspace_id, [ticked]),
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
    nothing = remember_turn_scope(workspace_id, [])
    first, _ = await tools.call(workspace_id, "render_document", render())

    script, read_refused = await tools.call(
        workspace_id,
        "read_document",
        {"artifact_id": _artifact_id(first)},
        token=nothing,
    )
    second, render_refused = await tools.call(
        workspace_id,
        "render_document",
        render(artifact_id=_artifact_id(first)),
        token=nothing,
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
        token=remember_turn_scope(workspace_id, [ticked]),
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
        token=remember_turn_scope(workspace_id, []),
    )

    assert is_error is True
    assert f"starts from template source {brand}, which is not selected" in text
    assert "ask them to select" in text
