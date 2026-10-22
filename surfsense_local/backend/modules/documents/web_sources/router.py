import asyncio

from fastapi import APIRouter, HTTPException, status

from api.dependencies import SessionDep, transact
from api.notify import notify_document_updates
from modules.documents.schemas import DocumentRead
from modules.documents.web_sources.background_pull.pending_sources import (
    pending_sources,
    sources_of_links,
)
from modules.documents.web_sources.background_pull.pull_task import pull_web_source
from modules.documents.web_sources.links import Route, routed
from modules.documents.web_sources.plugin_calls.http_refusals import as_http
from modules.documents.web_sources.plugin_calls.plugin_access import (
    LicenseRefusedError,
    plugin_access,
    require_plugin_access,
)
from modules.documents.web_sources.plugin_calls.plugin_call import (
    PluginUnavailableError,
    ToolRefusedError,
    call_plugin,
)
from modules.documents.web_sources.pullers.puller import Fit, Puller
from modules.documents.web_sources.rows.list_pages import list_page
from modules.documents.web_sources.rows.result_rows import result_row
from modules.documents.web_sources.rows.search_results import (
    GOOGLE_SEARCH,
    SCRAPE,
    listed_results,
    search_arguments,
)
from modules.documents.web_sources.schemas import (
    WebGroup,
    WebLinkDuplicate,
    WebLinkRejected,
    WebLinksAdd,
    WebLinksOpen,
    WebLinksOutcome,
    WebListPage,
    WebOpenRead,
    WebSearch,
    WebSearchRead,
)
from modules.embedding.dependencies import EMBEDDER_CHOSEN
from modules.events.dependencies import EventBrokerDep
from modules.workspaces.dependencies import WorkspaceDep

router = APIRouter(
    prefix="/workspaces/{workspace_id}/documents/web", tags=["documents"]
)

# Google Search may solve a captcha in a stealth browser first: up to 180 s a page.
SEARCH_SECONDS = 200


@router.post(
    "/search",
    response_model=WebSearchRead,
    summary="Search Google for links to add to Sources",
)
async def search_web(
    payload: WebSearch, workspace: WorkspaceDep, session: SessionDep
) -> WebSearchRead:
    """POST, so the app asks the network question: a search is the user's own action."""
    try:
        access = await transact(session, plugin_access, GOOGLE_SEARCH)
        items = await call_plugin(
            access, SCRAPE, search_arguments(payload.query), SEARCH_SECONDS
        )
    except (LicenseRefusedError, PluginUnavailableError, ToolRefusedError) as error:
        raise as_http(error) from error
    return WebSearchRead(results=listed_results(items))


@router.post(
    "/open",
    response_model=WebOpenRead,
    summary="Open pasted links into rows to add",
)
async def open_web_links(
    payload: WebLinksOpen, workspace: WorkspaceDep, session: SessionDep
) -> WebOpenRead:
    """A single link is a row titled by itself, with no call; a list opens into its items."""
    urls = list(dict.fromkeys(payload.urls))
    routes = {url: routed(url) for url in urls}
    singles = [url for url in urls if routes[url].fit != Fit.LIST]
    lists = [url for url in urls if routes[url].fit == Fit.LIST]
    groups: list[WebGroup] = []
    if singles:
        groups.append(
            WebGroup(
                link=None,
                results=[result_row(url, None, None) for url in singles],
                more=False,
                failed=False,
            )
        )
    if lists:
        groups += await _opened_lists(session, [(url, routes[url]) for url in lists])
    return WebOpenRead(groups=groups)


@router.post(
    "/list",
    response_model=WebGroup,
    summary="The next items of a list link",
)
async def list_web_link(
    payload: WebListPage, workspace: WorkspaceDep, session: SessionDep
) -> WebGroup:
    route = routed(payload.url)
    if route.fit != Fit.LIST:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "not a list link")
    [group] = await _opened_lists(session, [(payload.url, route)], payload.page)
    return group


async def _opened_lists(
    session: SessionDep, lists: list[tuple[str, Route]], page: int = 0
) -> list[WebGroup]:
    """The session's work first, one plugin at a time; then every list's call at once."""

    def accesses(s) -> dict:
        return {
            route.puller.plugin_id: plugin_access(s, route.puller.plugin_id)
            for _, route in lists
        }

    try:
        allowed = await transact(session, accesses)
    except LicenseRefusedError as error:
        raise as_http(error) from error
    return list(
        await asyncio.gather(
            *(
                list_page(
                    allowed[route.puller.plugin_id], route.puller.listing, url, page
                )
                for url, route in lists
                if route.puller.listing is not None
            )
        )
    )


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
    routes = {url: routed(url) for url in urls}
    rejected = [
        WebLinkRejected(url=url, reason=route.fit)
        for url, route in routes.items()
        if route.fit != Fit.ONE
    ]
    taken = [url for url, route in routes.items() if route.fit == Fit.ONE]
    known = await transact(session, sources_of_links, workspace.id, taken)
    links: list[tuple[str, Puller]] = [
        (url, routes[url].puller) for url in taken if url not in known
    ]

    def written(s) -> list:
        # The license and the plugin host's consent before anything is written.
        for plugin_id in dict.fromkeys(puller.plugin_id for _, puller in links):
            require_plugin_access(s, plugin_id)
        return pending_sources(s, workspace.id, links)

    try:
        notes = await transact(session, written) if links else []
    except LicenseRefusedError as error:
        raise as_http(error) from error
    for note in notes:
        pull_web_source(note.id)
        notify_document_updates(broker, note)
    return WebLinksOutcome(
        created=[DocumentRead.model_validate(note) for note in notes],
        duplicates=[
            WebLinkDuplicate(url=url, document_id=known[url])
            for url in taken
            if url in known
        ],
        rejected=rejected,
    )
