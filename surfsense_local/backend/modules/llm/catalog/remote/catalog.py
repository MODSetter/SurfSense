"""The remote catalog: the manifest and the user's connections, as rows.

Pure functions. Nothing here calls an endpoint: whoever fetched a connection's
listing hands it in, and a listing that failed is handed in as None.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from modules.llm.catalog.remote.classifier import classify
from modules.llm.catalog.remote.manifest.lookup import RemoteLookup
from modules.llm.catalog.remote.manifest.schema import Call, Connect, RemoteModel
from modules.llm.catalog.remote.rows import (
    CUSTOM,
    Availability,
    ConnectionInfo,
    ConnectionRef,
    ListedModel,
    RemoteRow,
)
from modules.llm.model_type import ModelType
from modules.llm.selectable import selectable_for

__all__ = ["ProviderSummary", "connection_rows", "provider_rows", "providers"]


@dataclass(frozen=True)
class ProviderSummary:
    id: str
    name: str
    doc: str | None
    connect: Connect
    type_counts: dict[ModelType, int]
    connections: int


def providers(lookup: RemoteLookup, connected: Mapping[str, int]) -> list[ProviderSummary]:
    """Every manifest provider, with how many models of each type it serves."""
    return [
        ProviderSummary(
            id=provider_id,
            name=provider.name,
            doc=provider.doc,
            connect=provider.connect,
            type_counts=dict(
                Counter(
                    model_type
                    for model_id, model in provider.models.items()
                    for model_type in classify(model_id, model)
                )
            ),
            connections=connected.get(provider_id, 0),
        )
        for provider_id, provider in lookup.manifest.providers.items()
    ]


def provider_rows(
    lookup: RemoteLookup, provider_id: str, connections: Sequence[ConnectionInfo]
) -> list[RemoteRow]:
    """One provider's models, offline: to add a key for, or one row per connection."""
    provider = lookup.manifest.providers[provider_id]
    targets = [ConnectionRef(c.id, c.label) for c in connections] or [None]
    return [
        _manifest_row(
            lookup,
            provider_id,
            model_id,
            model,
            target,
            Availability.UNCHECKED if target else Availability.NOT_CONNECTED,
        )
        for model_id, model in provider.models.items()
        for target in targets
    ]


def connection_rows(
    lookup: RemoteLookup,
    connection: ConnectionInfo,
    listing: Sequence[ListedModel] | None,
) -> list[RemoteRow]:
    """One connection's models, checked against its live listing."""
    ref = ConnectionRef(connection.id, connection.label)
    provider = (
        None
        if connection.catalog_provider == CUSTOM
        else lookup.manifest.providers.get(connection.catalog_provider)
    )
    if provider is None:
        return [_listed_row(connection.catalog_provider, ref, m) for m in listing or ()]

    if listing is None:
        return [
            _manifest_row(
                lookup, connection.catalog_provider, model_id, model, ref,
                Availability.COULD_NOT_CHECK,
            )
            for model_id, model in provider.models.items()
        ]

    # Gemini answers `models/<id>` and gateways prefix a vendor, so a listed id
    # matches a manifest entry whole or by its last segment.
    listed_as = {m.name: m.name for m in listing}
    listed_as.update({m.name.rsplit("/", 1)[-1]: m.name for m in listing})
    matched: set[str] = set()
    rows = []
    for model_id, model in provider.models.items():
        served = listed_as.get(model_id)
        if served is not None:
            matched.add(served)
        rows.append(
            _manifest_row(
                lookup, connection.catalog_provider, model_id, model, ref,
                Availability.AVAILABLE if served else Availability.NOT_SERVED,
            )
        )
    rows.extend(
        _listed_row(connection.catalog_provider, ref, m)
        for m in listing
        if m.name not in matched
    )
    return rows


def _manifest_row(
    lookup: RemoteLookup,
    provider_id: str,
    model_id: str,
    model: RemoteModel,
    connection: ConnectionRef | None,
    availability: Availability,
) -> RemoteRow:
    found = lookup.classify(model_id, provider=provider_id)
    connect = lookup.manifest.providers[provider_id].connect
    reason = connect.reason if connect.status == "unreachable" else _call_reason(model.call)
    if reason:
        availability = Availability.UNUSABLE
    return RemoteRow(
        provider=provider_id,
        connection=connection,
        model_id=model_id,
        name=model.name,
        types=found.types,
        known=found.known,
        selectable_for=()
        if availability is Availability.UNUSABLE
        else tuple(selectable_for(found.types, found.known)),
        supports=found.supports,
        status=model.status,
        availability=availability,
        reason=reason,
    )


def _listed_row(provider: str, connection: ConnectionRef, listed: ListedModel) -> RemoteRow:
    return RemoteRow(
        provider=provider,
        connection=connection,
        model_id=listed.name,
        name=listed.name,
        types=frozenset(listed.types),
        known=listed.known,
        selectable_for=tuple(selectable_for(listed.types, listed.known)),
        supports=None,
        status=None,
        availability=Availability.AVAILABLE,
    )


def _call_reason(call: Call | None) -> str | None:
    if call is None:
        return None
    if call.route == "responses":
        return "Only served on /responses, which SurfSense does not call yet"
    return f"Served through the {call.protocol} protocol, which SurfSense does not speak"
