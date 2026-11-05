from fastapi import APIRouter

from api.dependencies import SessionDep
from modules.documents.web_sources.web_search.search_server import (
    DEFAULT_SEARCH_SERVER,
    choose_search_server,
    chosen_search_server,
)
from modules.documents.web_sources.web_search.server_schemas import (
    SearchServerRead,
    SearchServerUpdate,
)

router = APIRouter(prefix="/web-search", tags=["documents"])


@router.get(
    "/server",
    response_model=SearchServerRead,
    summary="The SearXNG server Add from the web searches with",
)
def read_search_server(session: SessionDep) -> SearchServerRead:
    return SearchServerRead(
        url=chosen_search_server(session), default_url=DEFAULT_SEARCH_SERVER
    )


@router.put(
    "/server",
    response_model=SearchServerRead,
    summary="Search with another SearXNG server, or SurfSense's again",
)
def update_search_server(
    payload: SearchServerUpdate, session: SessionDep
) -> SearchServerRead:
    """Contacts nothing: the first search asks about the new server's host."""
    choose_search_server(session, payload.url)
    session.commit()
    return read_search_server(session)
