"""One-shot cutover: turn READY ``podcasts`` rows into Artifacts.

Run with --yes after deploying the artifact-aware podcast code and before the
migration that drops the row's audio columns. Safe to re-run: rows that already
produced an Artifact are skipped.

Streams the row's audio into the Artifact primary file, stamps
``podcasts.artifact_id``, and repoints the ``generate_podcast`` payloads held by
chat messages and public snapshots to carry the Artifact id.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from types import SimpleNamespace
from typing import Any

from sqlalchemy import text

from app.db import async_session_maker


async def _already_converted(session) -> dict[int, tuple[int, int]]:
    """Legacy podcast id -> (artifact id, workspace id), from an earlier run."""
    result = await session.execute(
        text(
            """
            SELECT (metadata -> 'legacy' ->> 'id')::int AS legacy_id,
                   id, workspace_id
            FROM artifacts
            WHERE format = 'podcast'
              AND metadata -> 'legacy' ->> 'kind' = 'podcast'
            """
        )
    )
    return {row.legacy_id: (row.id, row.workspace_id) for row in result}


async def _pending_rows(session) -> list[Any]:
    result = await session.execute(
        text(
            """
            SELECT id, workspace_id, title, storage_backend, storage_key,
                   file_location, podcast_transcript, thread_id
            FROM podcasts
            WHERE status = 'ready' AND artifact_id IS NULL
            ORDER BY id
            """
        )
    )
    return list(result)


def _tool_parts(content: Any):
    """Every ``generate_podcast`` tool-call part in a message."""
    if not isinstance(content, list):
        return
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "tool-call":
            continue
        if part.get("toolName") != "generate_podcast":
            continue
        if isinstance(part.get("result"), dict):
            yield part


async def _call_sites(session) -> dict[int, dict[str, Any]]:
    """Where each podcast was generated: thread and tool call, by legacy id."""
    result = await session.execute(
        text("SELECT id, thread_id, content FROM new_chat_messages")
    )
    sites: dict[int, dict[str, Any]] = {}
    for row in result:
        for part in _tool_parts(row.content):
            legacy_id = part["result"].get("podcast_id")
            if isinstance(legacy_id, int) and legacy_id not in sites:
                sites[legacy_id] = {
                    "thread_id": row.thread_id,
                    "tool_call_id": part.get("toolCallId"),
                }
    return sites


def _repoint(result: dict[str, Any], artifact_id: int, workspace_id: int):
    """Rewrite a stored tool payload to carry the Artifact id."""
    return {**result, "artifact_id": artifact_id, "workspace_id": workspace_id}


async def _repoint_messages(session, artifacts: dict[int, tuple[int, int]]) -> int:
    result = await session.execute(text("SELECT id, content FROM new_chat_messages"))
    rows = [(row.id, row.content) for row in result]

    updated = 0
    for message_id, content in rows:
        touched = False
        for part in _tool_parts(content):
            legacy_id = part["result"].get("podcast_id")
            mapping = artifacts.get(legacy_id) if isinstance(legacy_id, int) else None
            if mapping is None:
                continue
            part["result"] = _repoint(part["result"], *mapping)
            touched = True
        if touched:
            await session.execute(
                text(
                    "UPDATE new_chat_messages "
                    "SET content = CAST(:content AS jsonb) WHERE id = :id"
                ),
                {"content": json.dumps(content), "id": message_id},
            )
            updated += 1
    return updated


async def _repoint_snapshots(session, artifacts: dict[int, tuple[int, int]]) -> int:
    result = await session.execute(
        text("SELECT id, snapshot_data FROM public_chat_snapshots")
    )
    rows = [(row.id, row.snapshot_data) for row in result]

    updated = 0
    for snapshot_id, data in rows:
        if not isinstance(data, dict):
            continue
        touched = False
        shared_ids = set(data.get("artifact_ids") or [])
        for message in data.get("messages") or []:
            for part in _tool_parts(
                message.get("content") if isinstance(message, dict) else None
            ):
                legacy_id = part["result"].get("podcast_id")
                mapping = (
                    artifacts.get(legacy_id) if isinstance(legacy_id, int) else None
                )
                if mapping is None:
                    continue
                part["result"] = _repoint(part["result"], *mapping)
                shared_ids.add(mapping[0])
                touched = True
        if touched:
            data["artifact_ids"] = sorted(shared_ids)
            await session.execute(
                text(
                    "UPDATE public_chat_snapshots "
                    "SET snapshot_data = CAST(:data AS jsonb) WHERE id = :id"
                ),
                {"data": json.dumps(data), "id": snapshot_id},
            )
            updated += 1
    return updated


async def _load_audio(row) -> bytes:
    from app.file_storage.factory import get_storage_backend

    if row.storage_key:
        backend = get_storage_backend(row.storage_backend)
        return b"".join([chunk async for chunk in backend.open_stream(row.storage_key)])
    if row.file_location and os.path.isfile(row.file_location):
        with open(row.file_location, "rb") as handle:
            return handle.read()
    return b""


async def backfill(*, apply: bool) -> None:
    # Imported here: the artifact models register against ``app.db``, which
    # has to finish loading first.
    from app.artifacts.media.naming import primary_filename
    from app.artifacts.media.podcast.record import _representation_from_transcript
    from app.artifacts.persistence import ArtifactFileRole, ArtifactFormat
    from app.artifacts.schemas import ArtifactFileInput
    from app.artifacts.service import save_artifact
    from app.podcasts.service import read_transcript

    async def _record(session, row, site) -> int:
        title = row.title or "Podcast"
        audio = await _load_audio(row)
        if not audio:
            raise ValueError("no audio to convert")

        transcript = read_transcript(
            SimpleNamespace(podcast_transcript=row.podcast_transcript)
        )
        saved = await save_artifact(
            session,
            workspace_id=row.workspace_id,
            thread_id=site.get("thread_id") or row.thread_id,
            tool_call_id=site.get("tool_call_id"),
            title=title,
            markdown_representation=_representation_from_transcript(title, transcript),
            files=[
                ArtifactFileInput(
                    data=audio,
                    filename=primary_filename(
                        title, extension="mp3", fallback="podcast"
                    ),
                    mime_type="audio/mpeg",
                    role=ArtifactFileRole.PRIMARY,
                )
            ],
            extra_metadata={"legacy": {"kind": "podcast", "id": row.id}},
            format=ArtifactFormat.PODCAST,
        )
        return saved.artifact_id

    async with async_session_maker() as session:
        if (
            await session.execute(text("SELECT to_regclass('public.podcasts')"))
        ).scalar() is None:
            # Ran outside its window: 183 already renamed the table. That
            # migration is guarded, so an unconverted row can't slip past.
            print(
                "`podcasts` no longer exists (migration 183 renamed it to "
                "`podcast_runs`). Run this after 182 and before 183; nothing to do."
            )
            return

        rows = await _pending_rows(session)
        artifacts = await _already_converted(session)
        sites = await _call_sites(session)
        pending = [row for row in rows if row.id not in artifacts]

        # READY rows with a NULL column whose Artifact already exists (live path
        # before the column landed): stamp the link, don't re-create.
        strays = [row for row in rows if row.id in artifacts]

        print(
            f"{len(rows)} pending podcast row(s); {len(artifacts)} already converted."
        )
        if not apply:
            print(f"Dry run: {len(pending)} row(s) would become Artifacts.")
            if strays:
                print(f"{len(strays)} row(s) would just get their artifact_id stamped.")
            print("Re-run with --yes to convert them.")
            return

        for row in strays:
            await session.execute(
                text("UPDATE podcasts SET artifact_id = :aid WHERE id = :id"),
                {"aid": artifacts[row.id][0], "id": row.id},
            )
        if strays:
            await session.commit()
            print(f"Stamped artifact_id on {len(strays)} already-converted row(s).")

        failed = 0
        for row in pending:
            site = sites.get(row.id, {})
            try:
                artifact_id = await _record(session, row, site)
                await session.execute(
                    text("UPDATE podcasts SET artifact_id = :aid WHERE id = :id"),
                    {"aid": artifact_id, "id": row.id},
                )
                await session.commit()
                artifacts[row.id] = (artifact_id, row.workspace_id)
            except Exception as exc:
                await session.rollback()
                failed += 1
                print(f"  podcast {row.id}: FAILED ({exc})")

        print(f"Converted {len(pending) - failed} row(s); {failed} failed.")

        messages = await _repoint_messages(session, artifacts)
        snapshots = await _repoint_snapshots(session, artifacts)
        await session.commit()
        print(f"Repointed {messages} chat message(s) and {snapshots} snapshot(s).")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually convert. Without this flag the command is a dry run.",
    )
    args = parser.parse_args()
    await backfill(apply=args.yes)


if __name__ == "__main__":
    asyncio.run(main())
