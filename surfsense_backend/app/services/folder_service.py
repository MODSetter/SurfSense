"""Folder service: depth validation, circular reference checks, and position generation."""

from fastapi import HTTPException
from fractional_indexing import generate_key_between
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Folder

MAX_FOLDER_DEPTH = 8


async def get_folder_depth(session: AsyncSession, folder_id: int) -> int:
    """Return the depth of a folder (root-level = 1) using a recursive CTE."""
    result = await session.execute(
        text("""
            WITH RECURSIVE ancestors AS (
                SELECT id, parent_id, 1 AS depth
                FROM folders
                WHERE id = :folder_id
                UNION ALL
                SELECT f.id, f.parent_id, a.depth + 1
                FROM folders f
                JOIN ancestors a ON f.id = a.parent_id
            )
            SELECT MAX(depth) FROM ancestors;
        """),
        {"folder_id": folder_id},
    )
    return result.scalar() or 0


async def get_subtree_max_depth(session: AsyncSession, folder_id: int) -> int:
    """Return the maximum depth of any descendant below folder_id (0 if leaf)."""
    result = await session.execute(
        text("""
            WITH RECURSIVE descendants AS (
                SELECT id, 0 AS depth
                FROM folders
                WHERE parent_id = :folder_id
                UNION ALL
                SELECT f.id, d.depth + 1
                FROM folders f
                JOIN descendants d ON f.parent_id = d.id
            )
            SELECT COALESCE(MAX(depth), -1) FROM descendants;
        """),
        {"folder_id": folder_id},
    )
    val = result.scalar()
    return (val + 1) if val is not None and val >= 0 else 0


async def validate_folder_depth(
    session: AsyncSession,
    parent_id: int | None,
    subtree_depth: int = 0,
) -> None:
    """Raise 400 if placing a folder (with subtree) under parent_id would exceed MAX_FOLDER_DEPTH."""
    if parent_id is None:
        parent_depth = 0
    else:
        parent_depth = await get_folder_depth(session, parent_id)

    total = parent_depth + 1 + subtree_depth
    if total > MAX_FOLDER_DEPTH:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum folder nesting depth is {MAX_FOLDER_DEPTH}. "
            f"This operation would result in depth {total}.",
        )


async def check_no_circular_reference(
    session: AsyncSession,
    folder_id: int,
    new_parent_id: int | None,
) -> None:
    """Raise 400 if new_parent_id is folder_id itself or a descendant of folder_id."""
    if new_parent_id is None:
        return

    if new_parent_id == folder_id:
        raise HTTPException(
            status_code=400,
            detail="A folder cannot be moved into itself.",
        )

    result = await session.execute(
        text("""
            WITH RECURSIVE ancestors AS (
                SELECT id, parent_id
                FROM folders
                WHERE id = :new_parent_id
                UNION ALL
                SELECT f.id, f.parent_id
                FROM folders f
                JOIN ancestors a ON f.id = a.parent_id
            )
            SELECT 1 FROM ancestors WHERE id = :folder_id LIMIT 1;
        """),
        {"new_parent_id": new_parent_id, "folder_id": folder_id},
    )
    if result.scalar() is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot move a folder into one of its own descendants.",
        )


async def generate_folder_position(
    session: AsyncSession,
    search_space_id: int,
    parent_id: int | None,
    before_position: str | None = None,
    after_position: str | None = None,
) -> str:
    """Generate a fractional index key for ordering a folder among its siblings.

    - Default (no before/after): append after last sibling
    - Prepend: before_position=None, after_position=first sibling position
    - Insert between: both positions provided
    """
    if before_position is not None or after_position is not None:
        return generate_key_between(before_position, after_position)

    # Append after last sibling
    query = (
        select(Folder.position)
        .where(
            Folder.search_space_id == search_space_id,
            Folder.parent_id == parent_id
            if parent_id is not None
            else Folder.parent_id.is_(None),
        )
        .order_by(Folder.position.desc())
        .limit(1)
    )
    result = await session.execute(query)
    last_position = result.scalar()
    return generate_key_between(last_position, None)


async def ensure_folder_hierarchy_with_depth_validation(
    session: AsyncSession,
    search_space_id: int,
    path_segments: list[dict],
) -> Folder:
    """Create or return a nested folder chain, validating depth at each step.

    Each item in ``path_segments`` is a dict with:
      - ``name``  (str): folder display name
      - ``metadata`` (dict | None): optional ``folder_metadata`` JSONB payload

    Returns the deepest (leaf) Folder in the chain.
    """
    parent_id: int | None = None
    current_folder: Folder | None = None

    for segment in path_segments:
        name = segment["name"]
        metadata = segment.get("metadata")

        stmt = select(Folder).where(
            Folder.search_space_id == search_space_id,
            Folder.name == name,
            Folder.parent_id == parent_id
            if parent_id is not None
            else Folder.parent_id.is_(None),
        )
        result = await session.execute(stmt)
        folder = result.scalar_one_or_none()

        if folder is None:
            await validate_folder_depth(session, parent_id, subtree_depth=0)
            position = await generate_folder_position(
                session, search_space_id, parent_id
            )
            folder = Folder(
                name=name,
                search_space_id=search_space_id,
                parent_id=parent_id,
                position=position,
                folder_metadata=metadata,
            )
            session.add(folder)
            await session.flush()

        current_folder = folder
        parent_id = folder.id

    assert current_folder is not None, "path_segments must not be empty"
    return current_folder


async def get_folder_subtree_ids(session: AsyncSession, folder_id: int) -> list[int]:
    """Return all folder IDs in the subtree rooted at folder_id (inclusive)."""
    result = await session.execute(
        text("""
            WITH RECURSIVE subtree AS (
                SELECT id FROM folders WHERE id = :folder_id
                UNION ALL
                SELECT f.id FROM folders f JOIN subtree s ON f.parent_id = s.id
            )
            SELECT id FROM subtree;
        """),
        {"folder_id": folder_id},
    )
    return list(result.scalars().all())
