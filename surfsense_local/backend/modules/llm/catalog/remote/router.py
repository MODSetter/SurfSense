"""The remote catalog over HTTP: providers first, a provider's rows when opened.

All 8,000-odd remote rows in one response would be several megabytes, so the
providers come first and a provider's rows when it is opened. Only a
connection's own rows touch the network, and an endpoint that is down leaves
its rows unchecked rather than failing the request.
"""

from collections import Counter

import httpx
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.llm.catalog.remote.catalog import connection_rows, provider_rows, providers
from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.rows import ConnectionInfo, ListedModel, RemoteRow
from modules.llm.catalog.remote.schemas import RemoteProviderRead, RemoteRowRead
from modules.llm.connections.router import allowed_connection
from modules.llm.connections.service import discover_models
from modules.llm.models import ProviderConnection

router = APIRouter(prefix="/catalog/remote", tags=["catalog"])


def _connections(session: Session) -> list[ProviderConnection]:
    return list(session.scalars(select(ProviderConnection).order_by(ProviderConnection.label)))


def _info(connection: ProviderConnection) -> ConnectionInfo:
    return ConnectionInfo(connection.id, connection.label, connection.catalog_provider)


def _shown(rows: list[RemoteRow], include_deprecated: bool) -> list[RemoteRowRead]:
    # Hidden by default, still in the manifest, so a selection that uses a
    # deprecated model can say why it stopped working.
    return [
        RemoteRowRead.of(row)
        for row in rows
        if include_deprecated or row.status != "deprecated"
    ]


@router.get("", response_model=list[RemoteProviderRead], summary="List remote providers")
def list_providers(session: SessionDep) -> list[RemoteProviderRead]:
    connected = Counter(connection.catalog_provider for connection in _connections(session))
    return [RemoteProviderRead.of(summary) for summary in providers(remote_lookup(), connected)]


@router.get(
    "/providers/{provider_id}",
    response_model=list[RemoteRowRead],
    summary="List one remote provider's models, offline",
)
def read_provider(
    provider_id: str, session: SessionDep, include_deprecated: bool = False
) -> list[RemoteRowRead]:
    lookup = remote_lookup()
    if not lookup.has_provider(provider_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown provider: {provider_id}")
    connections = [
        _info(connection)
        for connection in _connections(session)
        if connection.catalog_provider == provider_id
    ]
    return _shown(provider_rows(lookup, provider_id, connections), include_deprecated)


@router.get(
    "/connections/{connection_id}",
    response_model=list[RemoteRowRead],
    summary="List a connection's models, checked against its live listing",
)
async def read_connection(
    connection_id: int, session: SessionDep, include_deprecated: bool = False
) -> list[RemoteRowRead]:
    connection = await transact(session, allowed_connection, connection_id)
    try:
        listing = [
            ListedModel(model.name, model.types, model.capability_known)
            for model in await discover_models(connection)
        ]
    except (httpx.HTTPError, ValueError):
        listing = None
    rows = connection_rows(remote_lookup(), _info(connection), listing)
    return _shown(rows, include_deprecated)
