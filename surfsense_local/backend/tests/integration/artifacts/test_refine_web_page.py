"""Refine for Studio's web pages: a page a model wrote is rewritten whole into the next version."""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.schemas import StudioJobCreate
from modules.artifacts.service import create_artifact_job
from modules.artifacts.web_pages.no_network import NO_NETWORK_POLICY
from modules.documents.models import Document, DocumentStatus
from modules.workspaces.models import Workspace
from shared.queue import studio_queue
from tests.integration.artifacts.test_refine import (  # noqa: F401
    _draft_reply,
    _primary,
    _refine,
    _refine_reply,
    _resolve,
    _window,
    _work_off,
    local_model,
)
from tests.integration.worker.conftest import stub_model  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("stub_model", "local_model"),
]

PAGE = (
    '<!doctype html><html lang="en"><head><title>Freight in 2026</title></head>'
    "<body><h1>Freight volume rose</h1><p>Volume rose 8% in Q3.</p></body></html>"
)
REVISED = PAGE.replace("Volume rose 8% in Q3.", "Volume rose 8%.")
META = f'<meta http-equiv="Content-Security-Policy" content="{NO_NETWORK_POLICY}">'


def _page_v1(
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    monkeypatch: pytest.MonkeyPatch,
    provider: str = "openai_compatible",
    reply: str = PAGE,
) -> Artifact:
    """Studio's Web page drafted by a model on a server, which writes the page itself."""
    _resolve(monkeypatch, provider)
    _draft_reply(monkeypatch, reply)
    artifact = create_artifact_job(
        session,
        workspace,
        StudioJobCreate(format="html", document_ids=[logo_source.id]),
    )
    _work_off(studio_queue)
    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    return artifact


async def test_a_written_page_keeps_its_html_as_its_spec_and_is_refinable(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The page as the model wrote it, without the policy SurfSense adds when storing it."""
    first = _page_v1(session, workspace, logo_source, monkeypatch)

    assert first.artifact_metadata["spec"] == {
        "kind": "html",
        "text": PAGE,
        "format": "html",
        "images": [],
    }
    page_id, workspace_id = first.id, workspace.id
    session.commit()
    listed = (await client.get(f"/workspaces/{workspace_id}/artifacts")).json()
    (page,) = [a for a in listed if a["id"] == page_id]
    assert (page["spec_kind"], page["refinable"]) == ("html", True)


async def test_refining_a_page_makes_the_next_version_from_the_rewritten_page(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One call holds the whole page and the instruction; v1 keeps its own page."""
    first = _page_v1(session, workspace, logo_source, monkeypatch)
    first_bytes = _primary(first)
    calls = _refine_reply(monkeypatch, f"```html\n{REVISED}\n```")

    response = await _refine(client, session, first.id, "Shorten the lede")

    assert response.status_code == 202, response.text
    assert response.json()["spec_kind"] == "html"
    _work_off(studio_queue)
    session.expire_all()
    second = session.get(Artifact, response.json()["id"])
    assert second.document.status is DocumentStatus.READY, second.document.error_message
    assert second.artifact_metadata["spec"]["text"] == REVISED
    assert _primary(second).decode().startswith(f"<!doctype html>{META}")
    assert "Volume rose 8%." in second.document.content
    (messages,) = calls
    assert PAGE in messages[-1].content
    assert "Shorten the lede" in messages[-1].content
    assert "How a page looks and moves" in messages[0].content
    assert _primary(first) == first_bytes


async def test_a_page_from_the_template_has_no_spec_to_refine(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model below the bar filled the template; there is no page of its own to rewrite."""
    first = _page_v1(
        session,
        workspace,
        logo_source,
        monkeypatch,
        provider="llamacpp",
        reply='{"title": "T", "sections": [{"heading": "H", "paragraphs": ["p"]}]}',
    )

    response = await _refine(client, session, first.id, "Shorten it")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_refinable"


async def test_the_design_guide_counts_against_the_window_a_page_refine_needs(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A short page in a small window is still refused: its prompt carries the whole guide."""
    first = _page_v1(session, workspace, logo_source, monkeypatch)
    _window(monkeypatch, 3_000)

    response = await _refine(client, session, first.id, "Shorten the lede")

    assert response.status_code == 409
    assert "too long for Qwen3-4B" in response.json()["detail"]
