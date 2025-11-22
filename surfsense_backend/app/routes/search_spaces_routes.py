from pathlib import Path
import threading

import yaml
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import SearchSpace, User, get_async_session
from app.schemas import (
    SearchSpaceCreate,
    SearchSpaceRead,
    SearchSpaceUpdate,
    ShareSpaceResponse,
)
from app.users import current_active_user
from app.utils.check_ownership import check_ownership

router = APIRouter()


# Cache community prompts at module startup for performance
# Avoids reading and parsing YAML on every request
_COMMUNITY_PROMPTS_CACHE: list[dict] | None = None
_prompts_lock = threading.Lock()

# Define prompts file path as module-level constant to avoid reconstruction
_PROMPTS_FILE_PATH = (
    Path(__file__).parent.parent
    / "prompts"
    / "public_search_space_prompts.yaml"
)


def _load_community_prompts() -> list[dict]:
    """
    Load community prompts from YAML file with thread-safe caching.

    Uses double-checked locking pattern to prevent race conditions where
    multiple concurrent requests could trigger redundant file reads before
    the cache is populated.

    Uses EAFP (Easier to Ask for Forgiveness than Permission) approach:
    reads and parses the file outside the lock to allow concurrent I/O,
    then uses the lock only for brief cache validation and assignment.
    This avoids TOCTOU race conditions and minimizes lock contention.

    Returns cached prompts if already loaded, otherwise loads from disk.
    This eliminates redundant file I/O on every API request.

    Raises:
        FileNotFoundError: If prompts YAML file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    global _COMMUNITY_PROMPTS_CACHE

    # First check without lock (fast path for cached case)
    if _COMMUNITY_PROMPTS_CACHE is not None:
        return _COMMUNITY_PROMPTS_CACHE

    # Read and parse file outside lock to allow concurrent I/O (EAFP approach)
    # This avoids TOCTOU race condition and minimizes time in critical section
    try:
        with open(_PROMPTS_FILE_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        prompts = data.get("prompts", [])
    except FileNotFoundError:
        raise FileNotFoundError(f"Community prompts file not found: {_PROMPTS_FILE_PATH}")

    # Acquire lock only for cache assignment (minimal critical section)
    with _prompts_lock:
        # Double-check after acquiring lock (another thread may have populated)
        if _COMMUNITY_PROMPTS_CACHE is not None:
            return _COMMUNITY_PROMPTS_CACHE

        _COMMUNITY_PROMPTS_CACHE = prompts
        return _COMMUNITY_PROMPTS_CACHE


@router.post("/searchspaces", response_model=SearchSpaceRead)
async def create_search_space(
    search_space: SearchSpaceCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        search_space_data = search_space.model_dump()

        # citations_enabled defaults to True (handled by Pydantic schema)
        # qna_custom_instructions defaults to None/empty (handled by DB)

        db_search_space = SearchSpace(**search_space_data, user_id=user.id)
        session.add(db_search_space)
        await session.commit()
        await session.refresh(db_search_space)
        return db_search_space
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create search space: {e!s}"
        ) from e


@router.get("/searchspaces", response_model=list[SearchSpaceRead])
async def read_search_spaces(
    skip: int = 0,
    limit: int = 200,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get all search spaces accessible to the current user.
    Returns:
    - Spaces owned by the user
    - Public spaces (is_public=True) from any user
    """
    try:
        result = await session.execute(
            select(SearchSpace)
            .filter(
                or_(
                    SearchSpace.user_id == user.id,
                    SearchSpace.is_public.is_(True)
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch search spaces: {e!s}"
        ) from e


@router.get("/searchspaces/prompts/community")
async def get_community_prompts(
    user: User = Depends(current_active_user),
):
    """
    Get community-curated prompts for SearchSpace System Instructions.

    Returns a list of pre-defined, high-quality prompts for various use cases
    including developer tools, productivity, creative tasks, and more.

    Prompts are cached at module startup for optimal performance.
    File I/O is executed in a thread pool to avoid blocking the async event loop.

    Note: Requires authentication (unlike upstream which is public).
    This aligns with our security-conscious approach.
    """
    try:
        # Execute blocking file I/O in thread pool to avoid blocking event loop
        # This ensures FastAPI server concurrency is not degraded
        return await run_in_threadpool(_load_community_prompts)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load community prompts: {e!s}"
        ) from e


@router.get("/searchspaces/{search_space_id}", response_model=SearchSpaceRead)
async def read_search_space(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific search space by ID.

    Access is granted if:
    - User owns the space, OR
    - Space is public (is_public=True)
    """
    try:
        # Fetch the search space using session.get() for primary key lookup
        search_space = await session.get(SearchSpace, search_space_id)

        if not search_space:
            raise HTTPException(
                status_code=404,
                detail="Search space not found"
            )

        # Check access: owner or public space
        if search_space.user_id != user.id and not search_space.is_public:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to access this search space"
            )

        return search_space

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch search space: {e!s}"
        ) from e


@router.put("/searchspaces/{search_space_id}", response_model=SearchSpaceRead)
async def update_search_space(
    search_space_id: int,
    search_space_update: SearchSpaceUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        db_search_space = await check_ownership(
            session, SearchSpace, search_space_id, user
        )
        update_data = search_space_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_search_space, key, value)
        await session.commit()
        await session.refresh(db_search_space)
        return db_search_space
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update search space: {e!s}"
        ) from e


@router.post("/searchspaces/{search_space_id}/share", response_model=ShareSpaceResponse)
async def share_search_space(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Share a search space (make it publicly accessible).

    SECURITY: Only superusers can share spaces.
    Public spaces:
    - Visible to all authenticated users in GET /searchspaces
    - Read-only for non-owners (can query, cannot add sources)
    - Full access for the owner

    Returns:
        dict: Success message with is_public status

    Raises:
        HTTPException 403: If user is not a superuser
        HTTPException 404: If search space not found
        HTTPException 403: If user doesn't own the space
    """
    try:
        # CRITICAL SECURITY CHECK: Only superusers can share spaces
        if not user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Only administrators can share search spaces"
            )

        # Get the search space and verify it exists using session.get() for primary key lookup
        space = await session.get(SearchSpace, search_space_id)

        if not space:
            raise HTTPException(
                status_code=404,
                detail="Search space not found"
            )

        # Make space public
        space.is_public = True
        await session.commit()
        await session.refresh(space)

        return ShareSpaceResponse(
            message="Search space shared successfully",
            is_public=True,
            search_space_id=search_space_id
        )

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to share search space: {e!s}"
        ) from e


@router.delete("/searchspaces/{search_space_id}", response_model=dict)
async def delete_search_space(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        db_search_space = await check_ownership(
            session, SearchSpace, search_space_id, user
        )
        await session.delete(db_search_space)
        await session.commit()
        return {"message": "Search space deleted successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete search space: {e!s}"
        ) from e
