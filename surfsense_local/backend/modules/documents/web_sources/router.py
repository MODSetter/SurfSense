from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from api.notify import notify_document_updates
from modules.documents.schemas import DocumentRead
from modules.documents.web_sources.background_pull.pending_sources import (
    pending_sources,
    sources_of_links,
)
from modules.documents.web_sources.background_pull.pull_task import pull_web_source
from modules.documents.web_sources.link_consent import (
    refused_link_hosts,
    refused_search_host,
)
from modules.documents.web_sources.links import routed
from modules.documents.web_sources.rows.result_rows import result_row
from modules.documents.web_sources.schemas import (
    WebLinkDuplicate,
    WebLinksAdd,
    WebLinksOpen,
    WebLinksOutcome,
    WebResults,
    WebSearch,
)
from modules.documents.web_sources.web_search.search_rows import search_rows
from modules.documents.web_sources.web_search.search_server import search_server
from modules.documents.web_sources.web_search.searxng import (
    SearchFailedError,
    SearchUnreachableError,
)
from modules.egress.last_calls import record_last_call
from modules.egress.service import EgressDeniedError, host_destination
from modules.embedding.dependencies import EMBEDDER_CHOSEN
from modules.events.dependencies import EventBrokerDep
from modules.workspaces.dependencies import WorkspaceDep

router = APIRouter(
    prefix="/workspaces/{workspace_id}/documents/web", tags=["documents"]
)


@router.post(
    "/search",
    response_model=WebResults,
    summary="Search the web, or YouTube, for links to add to Sources",
)
async def search_web(
    payload: WebSearch, workspace: WorkspaceDep, session: SessionDep
) -> WebResults:
    """POST, so the app asks the network question: a search is the user's own action."""

    def allowed_server(s: Session) -> tuple[str, EgressDeniedError | None]:
        server = search_server(s)
        refusal = refused_search_host(s, server)
        if refusal is None and (destination := host_destination(server)):
            record_last_call(s, destination)
        return server, refusal

    # Committed before raising, so a refused host stays listed in Settings > Network.
    server, refusal = await transact(session, allowed_server)
    if refusal is not None:
        raise refusal
    try:
        return await search_rows(server, payload.query, payload.source, payload.page)
    except SearchUnreachableError as error:
        raise _search_refusal("search_unreachable", server) from error
    except SearchFailedError as error:
        raise _search_refusal("search_failed", server) from error


# The dialog words each `code` itself, naming the server's host.
_SEARCH_REFUSALS = {
    "search_unreachable": "the search server could not be reached",
    "search_failed": "the search server answered without searching",
}


def _search_refusal(code: str, server: str) -> HTTPException:
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        {
            "code": code,
            "host": urlsplit(server).hostname,
            "message": _SEARCH_REFUSALS[code],
        },
    )


@router.post(
    "/open",
    response_model=WebResults,
    summary="Pasted links as rows to add",
)
async def open_web_links(payload: WebLinksOpen, workspace: WorkspaceDep) -> WebResults:
    """Each a row titled by itself, with no call: a preview would cost as much as the pull."""
    urls = list(dict.fromkeys(payload.urls))
    return WebResults(results=[result_row(url, None, None) for url in urls], more=False)


@router.post(
    "",
    response_model=WebLinksOutcome,
    dependencies=[EMBEDDER_CHOSEN],
    status_code=status.HTTP_201_CREATED,
    summary="Add links from the web to Sources",
)
async def add_web_links(
    payload: WebLinksAdd,
    workspace: WorkspaceDep,
    session: SessionDep,
    broker: EventBrokerDep,
) -> WebLinksOutcome:
    """Answers at once: each link is a pending source, pulled on the plugins queue."""
    urls = list(dict.fromkeys(payload.urls))
    known = await transact(session, sources_of_links, workspace.id, urls)
    links = [(url, routed(url)) for url in urls if url not in known]

    def written(s: Session) -> tuple[list, EgressDeniedError | None]:
        # Every host the reads start on, asked about before anything is written.
        refusal = refused_link_hosts(s, [url for url, _ in links])
        if refusal is not None:
            return [], refusal
        return pending_sources(s, workspace.id, links), None

    notes, refusal = await transact(session, written) if links else ([], None)
    if refusal is not None:
        raise refusal
    for note in notes:
        pull_web_source(note.id)
        notify_document_updates(broker, note)
    return WebLinksOutcome(
        created=[DocumentRead.model_validate(note) for note in notes],
        duplicates=[
            WebLinkDuplicate(url=url, document_id=known[url])
            for url in urls
            if url in known
        ],
    )
