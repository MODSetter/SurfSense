"""Resolve ``@connector`` account mentions into references for the pointer block."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSourceConnector
from app.schemas.new_chat import MentionedDocumentInfo

from .models import ConnectorReference


def connector_pointer_fields(
    *,
    account_name: str | None,
    connector_type: str | None,
    fallback_name: str | None,
) -> tuple[str, str | None]:
    """Pick the account label and provider for a connector pointer.

    Prefers the chip the user selected (``account_name`` / ``connector_type``)
    and falls back to the stored connector name.
    """
    label = account_name or fallback_name or "account"
    return label, connector_type or None


async def resolve_connector_references(
    session: AsyncSession,
    *,
    search_space_id: int,
    connector_ids: list[int],
    chips: list[MentionedDocumentInfo] | None = None,
) -> list[ConnectorReference]:
    """Map ``@connector`` ids to references; ids outside the space are dropped.

    The DB check only confirms the connector belongs to this search space;
    display fields come from the user's chip.
    """
    if not connector_ids:
        return []

    rows = await session.execute(
        select(
            SearchSourceConnector.id,
            SearchSourceConnector.name,
            SearchSourceConnector.connector_type,
        ).where(
            SearchSourceConnector.search_space_id == search_space_id,
            SearchSourceConnector.id.in_(connector_ids),
        )
    )
    accessible = {row.id: row for row in rows.all()}

    chip_by_id = {chip.id: chip for chip in (chips or []) if chip.kind == "connector"}

    references: list[ConnectorReference] = []
    for connector_id in dict.fromkeys(connector_ids):
        row = accessible.get(connector_id)
        if row is None:
            continue
        chip = chip_by_id.get(connector_id)
        stored_type = getattr(row.connector_type, "value", row.connector_type)
        label, provider = connector_pointer_fields(
            account_name=chip.account_name if chip else None,
            connector_type=(chip.connector_type if chip else None)
            or (str(stored_type) if stored_type else None),
            fallback_name=str(row.name or ""),
        )
        references.append(
            ConnectorReference(
                entity_id=connector_id,
                label=label,
                provider=provider,
            )
        )
    return references


__all__ = ["connector_pointer_fields", "resolve_connector_references"]
