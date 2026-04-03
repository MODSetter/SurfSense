"""Document versioning: snapshot creation and cleanup.

Rules:
- 30-minute debounce window: if the latest version was created < 30 min ago,
  overwrite it instead of creating a new row.
- Maximum 20 versions per document.
- Versions older than 90 days are cleaned up.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentVersion

MAX_VERSIONS_PER_DOCUMENT = 20
DEBOUNCE_MINUTES = 30
RETENTION_DAYS = 90


def _now() -> datetime:
    return datetime.now(UTC)


async def create_version_snapshot(
    session: AsyncSession,
    document: Document,
) -> DocumentVersion | None:
    """Snapshot the document's current state into a DocumentVersion row.

    Returns the created/updated DocumentVersion, or None if nothing was done.
    """
    now = _now()

    latest = (
        await session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if latest is not None:
        age = now - latest.created_at.replace(tzinfo=UTC)
        if age < timedelta(minutes=DEBOUNCE_MINUTES):
            latest.source_markdown = document.source_markdown
            latest.content_hash = document.content_hash
            latest.title = document.title
            latest.created_at = now
            await session.flush()
            return latest

    max_num = (
        await session.execute(
            select(func.coalesce(func.max(DocumentVersion.version_number), 0)).where(
                DocumentVersion.document_id == document.id
            )
        )
    ).scalar_one()

    version = DocumentVersion(
        document_id=document.id,
        version_number=max_num + 1,
        source_markdown=document.source_markdown,
        content_hash=document.content_hash,
        title=document.title,
        created_at=now,
    )
    session.add(version)
    await session.flush()

    # Cleanup: remove versions older than 90 days
    cutoff = now - timedelta(days=RETENTION_DAYS)
    await session.execute(
        delete(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.created_at < cutoff,
        )
    )

    # Cleanup: cap at MAX_VERSIONS_PER_DOCUMENT
    count = (
        await session.execute(
            select(func.count())
            .select_from(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
        )
    ).scalar_one()

    if count > MAX_VERSIONS_PER_DOCUMENT:
        excess = count - MAX_VERSIONS_PER_DOCUMENT
        oldest_ids_result = await session.execute(
            select(DocumentVersion.id)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.asc())
            .limit(excess)
        )
        oldest_ids = [row[0] for row in oldest_ids_result.all()]
        if oldest_ids:
            await session.execute(
                delete(DocumentVersion).where(DocumentVersion.id.in_(oldest_ids))
            )

    await session.flush()
    return version
