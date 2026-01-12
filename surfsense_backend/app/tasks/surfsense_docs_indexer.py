"""
Surfsense documentation indexer.
Indexes MDX documentation files at startup.
"""

import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import config
from app.db import SurfsenseDocsChunk, SurfsenseDocsDocument, async_session_maker

logger = logging.getLogger(__name__)

# Path to docs relative to project root
DOCS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "surfsense_web"
    / "content"
    / "docs"
)


def parse_mdx_frontmatter(content: str) -> tuple[str, str]:
    """
    Parse MDX file to extract frontmatter title and content.

    Args:
        content: Raw MDX file content

    Returns:
        Tuple of (title, content_without_frontmatter)
    """
    # Match frontmatter between --- markers
    frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n"
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if match:
        frontmatter = match.group(1)
        content_without_frontmatter = content[match.end() :]

        # Extract title from frontmatter
        title_match = re.search(r"^title:\s*(.+)$", frontmatter, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Untitled"

        # Remove quotes if present
        title = title.strip("\"'")

        return title, content_without_frontmatter.strip()

    return "Untitled", content.strip()


def get_all_mdx_files() -> list[Path]:
    """
    Get all MDX files from the docs directory.

    Returns:
        List of Path objects for each MDX file
    """
    if not DOCS_DIR.exists():
        logger.warning(f"Docs directory not found: {DOCS_DIR}")
        return []

    return list(DOCS_DIR.rglob("*.mdx"))


def generate_surfsense_docs_content_hash(content: str) -> str:
    """Generate SHA-256 hash for Surfsense docs content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_surfsense_docs_chunks(content: str) -> list[SurfsenseDocsChunk]:
    """
    Create chunks from Surfsense documentation content.

    Args:
        content: Document content to chunk

    Returns:
        List of SurfsenseDocsChunk objects with embeddings
    """
    return [
        SurfsenseDocsChunk(
            content=chunk.text,
            embedding=config.embedding_model_instance.embed(chunk.text),
        )
        for chunk in config.chunker_instance.chunk(content)
    ]


async def index_surfsense_docs(session: AsyncSession) -> tuple[int, int, int, int]:
    """
    Index all Surfsense documentation files.

    Args:
        session: SQLAlchemy async session

    Returns:
        Tuple of (created, updated, skipped, deleted) counts
    """
    created = 0
    updated = 0
    skipped = 0
    deleted = 0

    # Get all existing docs from database
    existing_docs_result = await session.execute(
        select(SurfsenseDocsDocument).options(
            selectinload(SurfsenseDocsDocument.chunks)
        )
    )
    existing_docs = {doc.source: doc for doc in existing_docs_result.scalars().all()}

    # Track which sources we've processed
    processed_sources = set()

    # Get all MDX files
    mdx_files = get_all_mdx_files()
    logger.info(f"Found {len(mdx_files)} MDX files to index")

    for mdx_file in mdx_files:
        try:
            source = str(mdx_file.relative_to(DOCS_DIR))
            processed_sources.add(source)

            # Read file content
            raw_content = mdx_file.read_text(encoding="utf-8")
            title, content = parse_mdx_frontmatter(raw_content)
            content_hash = generate_surfsense_docs_content_hash(raw_content)

            if source in existing_docs:
                existing_doc = existing_docs[source]

                # Check if content changed
                if existing_doc.content_hash == content_hash:
                    logger.debug(f"Skipping unchanged: {source}")
                    skipped += 1
                    continue

                # Content changed - update document
                logger.info(f"Updating changed document: {source}")

                # Create new chunks
                chunks = create_surfsense_docs_chunks(content)

                # Update document fields
                existing_doc.title = title
                existing_doc.content = content
                existing_doc.content_hash = content_hash
                existing_doc.embedding = config.embedding_model_instance.embed(content)
                existing_doc.chunks = chunks
                existing_doc.updated_at = datetime.now(UTC)

                updated += 1
            else:
                # New document - create it
                logger.info(f"Creating new document: {source}")

                chunks = create_surfsense_docs_chunks(content)

                document = SurfsenseDocsDocument(
                    source=source,
                    title=title,
                    content=content,
                    content_hash=content_hash,
                    embedding=config.embedding_model_instance.embed(content),
                    chunks=chunks,
                    updated_at=datetime.now(UTC),
                )

                session.add(document)
                created += 1

        except Exception as e:
            logger.error(f"Error processing {mdx_file}: {e}", exc_info=True)
            continue

    # Delete documents for removed files
    for source, doc in existing_docs.items():
        if source not in processed_sources:
            logger.info(f"Deleting removed document: {source}")
            await session.delete(doc)
            deleted += 1

    # Commit all changes
    await session.commit()

    logger.info(
        f"Indexing complete: {created} created, {updated} updated, "
        f"{skipped} skipped, {deleted} deleted"
    )

    return created, updated, skipped, deleted


async def seed_surfsense_docs() -> tuple[int, int, int, int]:
    """
    Seed Surfsense documentation into the database.

    This function indexes all MDX files from the docs directory.
    It handles creating, updating, and deleting docs based on content changes.

    Returns:
        Tuple of (created, updated, skipped, deleted) counts
        Returns (0, 0, 0, 0) if an error occurs
    """
    logger.info("Starting Surfsense docs indexing...")

    try:
        async with async_session_maker() as session:
            created, updated, skipped, deleted = await index_surfsense_docs(session)

        logger.info(
            f"Surfsense docs indexing complete: "
            f"created={created}, updated={updated}, skipped={skipped}, deleted={deleted}"
        )

        return created, updated, skipped, deleted

    except Exception as e:
        logger.error(f"Failed to seed Surfsense docs: {e}", exc_info=True)
        return 0, 0, 0, 0
