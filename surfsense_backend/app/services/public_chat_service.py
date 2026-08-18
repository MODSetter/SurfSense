"""
Service layer for public chat sharing via immutable snapshots.

Key concepts:
- Snapshots are frozen copies of a chat at a specific point in time
- Content hash enables deduplication (same content = same URL)
- Podcasts are embedded in snapshot_data for self-contained public views
- Single-phase clone reads directly from snapshot_data
"""

import contextlib
import hashlib
import json
import re
import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    ChatVisibility,
    NewChatMessage,
    NewChatThread,
    Permission,
    Podcast,
    PodcastStatus,
    PublicChatSnapshot,
    User,
    WorkspaceMembership,
)
from app.utils.rbac import check_permission

UI_TOOLS = {
    "generate_image",
    "generate_podcast",
    "generate_video_presentation",
}
LEGACY_STATIC_UI_TOOLS = {"generate_report", "generate_resume"}


def strip_citations(text: str) -> str:
    """
    Remove [citation:X] and [citation:doc-X] patterns from text.
    Preserves newlines to maintain markdown formatting.
    """
    # Remove citation patterns
    text = re.sub(r"[\[【]\u200B?citation:(doc-)?\d+\u200B?[\]】]", "", text)
    # Collapse multiple spaces/tabs (but NOT newlines) into single space
    text = re.sub(r"[^\S\n]+", " ", text)
    # Normalize excessive blank lines (3+ newlines → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Clean up spaces around newlines
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def sanitize_content_for_public(content: list | str | None) -> list:
    """
    Filter message content for public view.
    Strips citations and filters to UI-relevant tools.
    """
    if content is None:
        return []

    if isinstance(content, str):
        clean_text = strip_citations(content)
        return [{"type": "text", "text": clean_text}] if clean_text else []

    if not isinstance(content, list):
        return []

    sanitized = []
    for part in content:
        if not isinstance(part, dict):
            continue

        part_type = part.get("type")

        if part_type == "text":
            clean_text = strip_citations(part.get("text", ""))
            if clean_text:
                sanitized.append({"type": "text", "text": clean_text})

        elif part_type == "tool-call":
            tool_name = part.get("toolName")
            if tool_name not in UI_TOOLS and tool_name not in LEGACY_STATIC_UI_TOOLS:
                continue
            sanitized.append(part)

    return sanitized


async def get_author_display(
    session: AsyncSession,
    author_id: UUID | None,
    user_cache: dict[UUID, dict],
) -> dict | None:
    """Transform author UUID to display info."""
    if author_id is None:
        return None

    if author_id not in user_cache:
        result = await session.execute(select(User).filter(User.id == author_id))
        user = result.scalars().first()
        if user:
            user_cache[author_id] = {
                "display_name": user.display_name or "User",
                "avatar_url": user.avatar_url,
            }
        else:
            user_cache[author_id] = {
                "display_name": "Unknown User",
                "avatar_url": None,
            }

    return user_cache[author_id]


# =============================================================================
# Content Hashing
# =============================================================================


def compute_content_hash(messages: list[dict]) -> str:
    """
    Compute SHA-256 hash of message content for deduplication.

    The hash is based on message IDs and content, ensuring that:
    - Same messages = same hash = same URL (deduplication)
    - Any change = different hash = new URL
    """
    # Sort by message ID to ensure consistent ordering
    sorted_messages = sorted(messages, key=lambda m: m.get("id", 0))

    # Create normalized representation
    normalized = []
    for msg in sorted_messages:
        normalized.append(
            {
                "id": msg.get("id"),
                "role": msg.get("role"),
                "content": msg.get("content"),
            }
        )

    content_str = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content_str.encode()).hexdigest()


# =============================================================================
# Snapshot Creation
# =============================================================================


async def create_snapshot(
    session: AsyncSession,
    thread_id: int,
    auth: AuthContext,
) -> dict:
    user = auth.user
    """
    Create a public snapshot of a chat thread.

    Returns existing snapshot if content unchanged (same hash).
    Returns new snapshot with unique URL if content changed.
    """
    from app.config import config

    frontend_url = (config.NEXT_FRONTEND_URL or "").rstrip("/")
    result = await session.execute(
        select(NewChatThread)
        .options(selectinload(NewChatThread.messages))
        .filter(NewChatThread.id == thread_id)
    )
    thread = result.scalars().first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await check_permission(
        session,
        auth,
        thread.workspace_id,
        Permission.PUBLIC_SHARING_CREATE.value,
        "You don't have permission to create public share links",
    )

    # Build snapshot data
    user_cache: dict[UUID, dict] = {}
    messages_data = []
    message_ids = []
    podcasts_data = []
    podcast_ids_seen: set[int] = set()
    artifact_ids: set[int] = set()

    for msg in sorted(thread.messages, key=lambda m: m.created_at):
        author = await get_author_display(session, msg.author_id, user_cache)
        sanitized_content = sanitize_content_for_public(msg.content)

        # Extract podcast references and update status to "ready" for completed ones.
        # Legacy report/resume tool-call parts remain untouched for static card rendering.
        if isinstance(sanitized_content, list):
            for part in sanitized_content:
                if not isinstance(part, dict) or part.get("type") != "tool-call":
                    continue

                tool_name = part.get("toolName")

                # The artifacts this share is allowed to serve to anonymous
                # viewers; anything else stays behind the session.
                shared_result = part.get("result")
                if isinstance(shared_result, dict) and isinstance(
                    shared_result.get("artifact_id"), int
                ):
                    artifact_ids.add(shared_result["artifact_id"])

                if tool_name == "generate_podcast":
                    result_data = part.get("result", {})
                    podcast_id = result_data.get("podcast_id")
                    if podcast_id and podcast_id not in podcast_ids_seen:
                        podcast_info = await _get_podcast_for_snapshot(
                            session, podcast_id
                        )
                        if podcast_info:
                            podcasts_data.append(podcast_info)
                            podcast_ids_seen.add(podcast_id)
                            # The tool result carries podcast_id, not artifact_id,
                            # so the generic allowlist check above misses it.
                            new_result = {**result_data, "status": "ready"}
                            artifact_id = podcast_info.get("artifact_id")
                            if isinstance(artifact_id, int):
                                artifact_ids.add(artifact_id)
                                new_result["artifact_id"] = artifact_id
                                new_result["workspace_id"] = podcast_info.get(
                                    "workspace_id"
                                )
                            part["result"] = new_result

        messages_data.append(
            {
                "id": msg.id,
                "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                "content": sanitized_content,
                "author": author,
                "author_id": str(msg.author_id) if msg.author_id else None,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
        )
        message_ids.append(msg.id)

    if not messages_data:
        raise HTTPException(status_code=400, detail="Cannot share an empty chat")

    # Compute content hash for deduplication
    content_hash = compute_content_hash(messages_data)

    # Check if identical snapshot already exists
    existing_result = await session.execute(
        select(PublicChatSnapshot).filter(
            PublicChatSnapshot.thread_id == thread_id,
            PublicChatSnapshot.content_hash == content_hash,
        )
    )
    existing = existing_result.scalars().first()

    if existing:
        # Return existing snapshot URL
        return {
            "snapshot_id": existing.id,
            "share_token": existing.share_token,
            "public_url": f"{frontend_url}/public/{existing.share_token}",
            "is_new": False,
        }

    # Get thread author info
    thread_author = await get_author_display(session, thread.created_by_id, user_cache)

    # Create snapshot data
    snapshot_data = {
        "title": thread.title,
        "snapshot_at": datetime.now(UTC).isoformat(),
        "author": thread_author,
        "messages": messages_data,
        "podcasts": podcasts_data,
        "artifact_ids": sorted(artifact_ids),
    }

    # Create new snapshot
    share_token = secrets.token_urlsafe(48)
    snapshot = PublicChatSnapshot(
        thread_id=thread_id,
        share_token=share_token,
        content_hash=content_hash,
        snapshot_data=snapshot_data,
        message_ids=message_ids,
        created_by_user_id=user.id,
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)

    return {
        "snapshot_id": snapshot.id,
        "share_token": snapshot.share_token,
        "public_url": f"{frontend_url}/public/{snapshot.share_token}",
        "is_new": True,
    }


async def _get_podcast_for_snapshot(
    session: AsyncSession,
    podcast_id: int,
) -> dict | None:
    """Get podcast info for embedding in snapshot_data."""
    result = await session.execute(select(Podcast).filter(Podcast.id == podcast_id))
    podcast = result.scalars().first()

    if not podcast or podcast.status != PodcastStatus.READY:
        return None

    # Audio is served from the Artifact; only the transcript stays embedded.
    return {
        "original_id": podcast.id,
        "title": podcast.title,
        "transcript": podcast.podcast_transcript,
        "artifact_id": podcast.artifact_id,
        "workspace_id": podcast.workspace_id,
    }


# =============================================================================
# Snapshot Retrieval
# =============================================================================


async def get_snapshot_by_token(
    session: AsyncSession,
    share_token: str,
) -> PublicChatSnapshot | None:
    """Get a snapshot by its share token."""
    result = await session.execute(
        select(PublicChatSnapshot).filter(PublicChatSnapshot.share_token == share_token)
    )
    return result.scalars().first()


async def get_public_chat(
    session: AsyncSession,
    share_token: str,
) -> dict:
    """
    Get public chat data from a snapshot.

    Returns sanitized content suitable for public viewing.
    """
    snapshot = await get_snapshot_by_token(session, share_token)

    if not snapshot:
        raise HTTPException(status_code=404, detail="Not found")

    data = snapshot.snapshot_data

    return {
        "thread": {
            "title": data.get("title", "Untitled"),
            "created_at": data.get("snapshot_at"),
        },
        "messages": data.get("messages", []),
    }


async def list_snapshots_for_thread(
    session: AsyncSession,
    thread_id: int,
    auth: AuthContext,
) -> list[dict]:
    """List all public snapshots for a thread."""
    from app.config import config

    result = await session.execute(
        select(NewChatThread).filter(NewChatThread.id == thread_id)
    )
    thread = result.scalars().first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Check permission to view public share links
    await check_permission(
        session,
        auth,
        thread.workspace_id,
        Permission.PUBLIC_SHARING_VIEW.value,
        "You don't have permission to view public share links",
    )

    result = await session.execute(
        select(PublicChatSnapshot)
        .filter(PublicChatSnapshot.thread_id == thread_id)
        .order_by(PublicChatSnapshot.created_at.desc())
    )
    snapshots = result.scalars().all()

    frontend_url = (config.NEXT_FRONTEND_URL or "").rstrip("/")

    return [
        {
            "id": s.id,
            "share_token": s.share_token,
            "public_url": f"{frontend_url}/public/{s.share_token}",
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "message_count": len(s.message_ids) if s.message_ids else 0,
        }
        for s in snapshots
    ]


async def list_snapshots_for_workspace(
    session: AsyncSession,
    workspace_id: int,
    auth: AuthContext,
) -> list[dict]:
    """List all public snapshots for a workspace."""
    from app.config import config

    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.PUBLIC_SHARING_VIEW.value,
        "You don't have permission to view public share links",
    )

    result = await session.execute(
        select(PublicChatSnapshot)
        .join(NewChatThread, PublicChatSnapshot.thread_id == NewChatThread.id)
        .filter(NewChatThread.workspace_id == workspace_id)
        .order_by(PublicChatSnapshot.created_at.desc())
    )
    snapshots = result.scalars().all()

    snapshot_thread_ids = [s.thread_id for s in snapshots]
    thread_result = await session.execute(
        select(NewChatThread.id, NewChatThread.title).filter(
            NewChatThread.id.in_(snapshot_thread_ids)
        )
    )
    thread_titles = {row[0]: row[1] for row in thread_result.fetchall()}

    frontend_url = (config.NEXT_FRONTEND_URL or "").rstrip("/")

    return [
        {
            "id": s.id,
            "share_token": s.share_token,
            "public_url": f"{frontend_url}/public/{s.share_token}",
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "message_count": len(s.message_ids) if s.message_ids else 0,
            "thread_id": s.thread_id,
            "thread_title": thread_titles.get(s.thread_id, "Untitled"),
            "created_by_user_id": str(s.created_by_user_id)
            if s.created_by_user_id
            else None,
        }
        for s in snapshots
    ]


# =============================================================================
# Snapshot Deletion
# =============================================================================


async def delete_snapshot(
    session: AsyncSession,
    thread_id: int,
    snapshot_id: int,
    auth: AuthContext,
) -> bool:
    """Delete a specific snapshot. Only thread owner can delete."""
    # Get snapshot with thread
    result = await session.execute(
        select(PublicChatSnapshot)
        .options(selectinload(PublicChatSnapshot.thread))
        .filter(
            PublicChatSnapshot.id == snapshot_id,
            PublicChatSnapshot.thread_id == thread_id,
        )
    )
    snapshot = result.scalars().first()

    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    await check_permission(
        session,
        auth,
        snapshot.thread.workspace_id,
        Permission.PUBLIC_SHARING_DELETE.value,
        "You don't have permission to delete public share links",
    )

    await session.delete(snapshot)
    await session.commit()
    return True


async def delete_affected_snapshots(
    session: AsyncSession,
    thread_id: int,
    message_ids: list[int],
) -> int:
    """
    Delete snapshots that contain any of the given message IDs.

    Called when messages are edited/deleted/regenerated.
    Uses independent session to work reliably in streaming response cleanup.
    """
    if not message_ids:
        return 0

    from sqlalchemy.dialects.postgresql import array

    from app.db import async_session_maker

    async with async_session_maker() as independent_session:
        result = await independent_session.execute(
            delete(PublicChatSnapshot)
            .where(PublicChatSnapshot.thread_id == thread_id)
            .where(PublicChatSnapshot.message_ids.op("&&")(array(message_ids)))
            .returning(PublicChatSnapshot.id)
        )

        deleted_ids = result.scalars().all()
        await independent_session.commit()

        return len(deleted_ids)


# =============================================================================
# Cloning from Snapshot
# =============================================================================


async def get_user_default_workspace(
    session: AsyncSession,
    user_id: UUID,
) -> int | None:
    """
    Get user's default workspace for cloning.

    Returns the first workspace where user is owner, or None if not found.
    """
    result = await session.execute(
        select(WorkspaceMembership)
        .filter(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.is_owner.is_(True),
        )
        .limit(1)
    )
    membership = result.scalars().first()

    if membership:
        return membership.workspace_id

    return None


async def clone_from_snapshot(
    session: AsyncSession,
    share_token: str,
    user: User,
) -> dict:
    """
    Copy messages and podcasts from source thread to target thread.

    Creates thread and copies messages from snapshot_data.
    When encountering generate_podcast tool-calls, creates cloned podcast records
    and updates the podcast_id references inline.
    Returns the new thread info.
    """
    import copy

    snapshot = await get_snapshot_by_token(session, share_token)

    if not snapshot:
        raise HTTPException(
            status_code=404, detail="Chat not found or no longer public"
        )

    target_workspace_id = await get_user_default_workspace(session, user.id)

    if target_workspace_id is None:
        raise HTTPException(status_code=400, detail="No workspace found for user")

    data = snapshot.snapshot_data
    messages_data = data.get("messages", [])

    new_thread = NewChatThread(
        title=data.get("title", "Cloned Chat"),
        archived=False,
        visibility=ChatVisibility.PRIVATE,
        workspace_id=target_workspace_id,
        created_by_id=user.id,
        cloned_from_thread_id=snapshot.thread_id,
        cloned_from_snapshot_id=snapshot.id,
        cloned_at=datetime.now(UTC),
        needs_history_bootstrap=True,
    )
    session.add(new_thread)
    await session.flush()

    # Check which authors from snapshot still exist in DB
    author_ids_from_snapshot: set[UUID] = set()
    for msg_data in messages_data:
        if author_str := msg_data.get("author_id"):
            with contextlib.suppress(ValueError, TypeError):
                author_ids_from_snapshot.add(UUID(author_str))

    existing_authors: set[UUID] = set()
    if author_ids_from_snapshot:
        result = await session.execute(
            select(User.id).where(User.id.in_(author_ids_from_snapshot))
        )
        existing_authors = {row[0] for row in result.fetchall()}

    for msg_data in messages_data:
        role = msg_data.get("role", "user")

        # Use original author if exists, otherwise None
        author_id = None
        if author_str := msg_data.get("author_id"):
            try:
                parsed_id = UUID(author_str)
                if parsed_id in existing_authors:
                    author_id = parsed_id
            except (ValueError, TypeError):
                pass

        content = copy.deepcopy(msg_data.get("content", []))

        new_message = NewChatMessage(
            thread_id=new_thread.id,
            role=role,
            content=content,
            author_id=author_id,
        )
        session.add(new_message)

    await session.commit()
    await session.refresh(new_thread)

    return {
        "thread_id": new_thread.id,
        "workspace_id": target_workspace_id,
    }


async def get_snapshot_podcast(
    session: AsyncSession,
    share_token: str,
    podcast_id: int,
) -> dict | None:
    """
    Get podcast info from a snapshot by original podcast ID.

    Used for streaming podcast audio from public view.
    Looks up the podcast by its original_id in the snapshot's podcasts array.
    """
    snapshot = await get_snapshot_by_token(session, share_token)

    if not snapshot:
        return None

    podcasts = snapshot.snapshot_data.get("podcasts", [])

    # Find podcast by original_id
    for podcast in podcasts:
        if podcast.get("original_id") == podcast_id:
            return podcast

    return None


async def get_snapshot_artifact_file(
    session: AsyncSession,
    share_token: str,
    artifact_id: int,
):
    """Primary file of an artifact this snapshot actually references.

    The snapshot's ``artifact_ids`` is the allowlist: a share token grants
    access to the artifacts produced in that thread, not to every artifact
    in the workspace.
    """
    from app.artifacts.persistence import ArtifactFile, ArtifactFileRole

    snapshot = await get_snapshot_by_token(session, share_token)
    if not snapshot:
        return None

    allowed = snapshot.snapshot_data.get("artifact_ids") or []
    if artifact_id not in allowed:
        return None

    result = await session.execute(
        select(ArtifactFile).filter(
            ArtifactFile.artifact_id == artifact_id,
            ArtifactFile.role == ArtifactFileRole.PRIMARY,
        )
    )
    return result.scalars().first()


async def get_snapshot_video_artifact(
    session: AsyncSession,
    share_token: str,
    artifact_id: int,
):
    """Video Artifact this snapshot references, or ``None``.

    Same allowlist as ``get_snapshot_artifact_file``: the share token grants
    access only to the artifacts the shared thread produced. Returns the
    Artifact with its document loaded (for the title); the Remotion slides and
    scene codes live in ``artifact_metadata``.
    """
    from app.artifacts.persistence import Artifact

    snapshot = await get_snapshot_by_token(session, share_token)
    if not snapshot:
        return None

    allowed = snapshot.snapshot_data.get("artifact_ids") or []
    if artifact_id not in allowed:
        return None

    result = await session.execute(
        select(Artifact)
        .options(selectinload(Artifact.document))
        .filter(Artifact.id == artifact_id, Artifact.format == "video")
    )
    return result.scalars().first()


async def get_snapshot_video_presentation(
    session: AsyncSession,
    share_token: str,
    video_presentation_id: int,
) -> dict | None:
    """
    Get video presentation info from a snapshot by original video presentation ID.

    Used for rendering video presentation in public view.
    Looks up the presentation by its original_id in the snapshot's video_presentations array.
    """
    snapshot = await get_snapshot_by_token(session, share_token)

    if not snapshot:
        return None

    video_presentations = snapshot.snapshot_data.get("video_presentations", [])

    for vp in video_presentations:
        if vp.get("original_id") == video_presentation_id:
            return vp

    return None
