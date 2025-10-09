from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.elasticsearch_connector import ElasticsearchConnector
from app.db import Chunk, Document, DocumentType, SearchSourceConnector


@dataclass(slots=True)
class ElasticsearchSearchParams:
    indices: Sequence[str] | None
    query: str
    search_fields: Sequence[str] | None
    max_documents: int
    start_date: str | None = None
    end_date: str | None = None


def _coerce_sequence(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
        return items or None
    if isinstance(value, Iterable):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or None
    return None


def _format_content(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


async def index_elasticsearch_documents(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None,
    end_date: str | None,
    *,
    update_last_indexed: bool = True,
) -> tuple[int, str | None]:
    connector = await session.get(SearchSourceConnector, connector_id)
    if connector is None:
        return 0, f"Connector {connector_id} not found."

    config = connector.config or {}
    params = ElasticsearchSearchParams(
        indices=_coerce_sequence(config.get("indices")),
        query=str(config.get("query") or "*"),
        search_fields=_coerce_sequence(config.get("search_fields")),
        max_documents=int(config.get("max_documents") or 1000),
        start_date=start_date,
        end_date=end_date,
    )

    try:
        async with ElasticsearchConnector(config) as elastic:
            hits = await elastic.search_documents(
                indices=params.indices,
                query=params.query,
                search_fields=params.search_fields,
                max_documents=params.max_documents,
            )
    except Exception as exc:
        return 0, f"Elasticsearch query failed: {exc!s}"

    documents_processed = 0
    ingested_at = datetime.now(UTC).isoformat()

    try:
        for hit in hits:
            source = hit.get("_source") or {}
            content = _format_content(source)
            content_hash = sha256(
                f"{hit.get('_index', '')}::{hit.get('_id', '')}::{content}".encode()
            ).hexdigest()

            existing = await session.execute(
                select(Document).where(
                    Document.search_space_id == search_space_id,
                    Document.content_hash == content_hash,
                )
            )
            if existing.scalar_one_or_none():
                continue

            title = str(
                source.get("title")
                or source.get("name")
                or hit.get("_id")
                or "Elasticsearch Document"
            )

            document_metadata = {
                "connector_id": connector_id,
                "connector_name": connector.name,
                "source": "elasticsearch",
                "index": hit.get("_index"),
                "document_id": hit.get("_id"),
                "score": hit.get("_score"),
                "search_parameters": {
                    "indices": params.indices,
                    "query": params.query,
                    "search_fields": params.search_fields,
                    "start_date": params.start_date,
                    "end_date": params.end_date,
                },
                "ingested_at": ingested_at,
            }

            new_document = Document(
                title=title,
                document_type=DocumentType.ELASTICSEARCH_CONNECTOR,
                document_metadata=document_metadata,
                content=content,
                content_hash=content_hash,
                search_space_id=search_space_id,
            )
            session.add(new_document)
            await session.flush()

            chunk = Chunk(content=content, document_id=new_document.id)
            session.add(chunk)

            documents_processed += 1

        await session.commit()
        return documents_processed, None
    except Exception as exc:
        await session.rollback()
        return 0, f"Failed to index Elasticsearch documents: {exc!s}"
