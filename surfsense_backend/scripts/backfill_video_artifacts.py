"""One-shot cutover: turn READY ``video_presentations`` rows into Artifacts.

Run with --yes after deploying the artifact-aware video code and before the
migration that drops ``slides`` / ``scene_codes``. Safe to re-run: rows that
already produced an Artifact are skipped.

Copies the Remotion ``slides`` and ``scene_codes`` into ``artifact_metadata``,
carries the first offloaded slide audio as the primary file (rows whose audio
predates the object-store offload get an artifact with no audio, which still
renders), stamps ``video_presentations.artifact_id``, and repoints the
``generate_video_presentation`` payloads held by chat messages and public
snapshots to carry the Artifact id.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import text

from app.db import async_session_maker


async def _already_converted(session) -> dict[int, tuple[int, int]]:
    """Legacy video id -> (artifact id, workspace id), from an earlier run."""
    result = await session.execute(
        text(
            """
            SELECT (metadata -> 'legacy' ->> 'id')::int AS legacy_id,
                   id, workspace_id
            FROM artifacts
            WHERE format = 'video'
              AND metadata -> 'legacy' ->> 'kind' = 'video'
            """
        )
    )
    return {row.legacy_id: (row.id, row.workspace_id) for row in result}


async def _pending_rows(session) -> list[Any]:
    result = await session.execute(
        text(
            """
            SELECT id, workspace_id, title, slides, scene_codes, thread_id
            FROM video_presentations
            WHERE status = 'ready' AND artifact_id IS NULL
            ORDER BY id
            """
        )
    )
    return list(result)


def _tool_parts(content: Any):
    """Every ``generate_video_presentation`` tool-call part in a message."""
    if not isinstance(content, list):
        return
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "tool-call":
            continue
        if part.get("toolName") != "generate_video_presentation":
            continue
        if isinstance(part.get("result"), dict):
            yield part


async def _call_sites(session) -> dict[int, dict[str, Any]]:
    """Where each video was generated: thread and tool call, by legacy id."""
    result = await session.execute(
        text("SELECT id, thread_id, content FROM new_chat_messages")
    )
    sites: dict[int, dict[str, Any]] = {}
    for row in result:
        for part in _tool_parts(row.content):
            legacy_id = part["result"].get("video_presentation_id")
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
            legacy_id = part["result"].get("video_presentation_id")
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
                legacy_id = part["result"].get("video_presentation_id")
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


async def backfill(*, apply: bool) -> None:
    # Imported here: the artifact models register against ``app.db``, which
    # has to finish loading first.
    from app.artifacts.media.naming import primary_filename
    from app.artifacts.media.video.storage import open_stream
    from app.artifacts.persistence import ArtifactFileRole, ArtifactFormat
    from app.artifacts.schemas import ArtifactFileInput
    from app.artifacts.service import save_artifact

    async def _record(session, row, site) -> int:
        slides = row.slides or []
        scene_codes = row.scene_codes or []
        title = row.title or "Video presentation"

        audio_key = next(
            (s.get("audio_storage_key") for s in slides if s.get("audio_storage_key")),
            None,
        )
        files: list[ArtifactFileInput] = []
        if audio_key:
            chunks = [chunk async for chunk in open_stream(audio_key)]
            audio = b"".join(chunks)
            if audio:
                files = [
                    ArtifactFileInput(
                        data=audio,
                        filename=primary_filename(
                            title, extension="mp3", fallback="slide-1-audio"
                        ),
                        mime_type="audio/mpeg",
                        role=ArtifactFileRole.PRIMARY,
                    )
                ]

        remotion_slides = [
            {k: v for k, v in s.items() if k not in {"audio_file", "storage_backend"}}
            for s in slides
        ]
        outline = "\n".join(
            f"- Slide {s.get('slide_number')}: "
            f"{s.get('title') or s.get('heading') or 'Untitled'}"
            for s in slides
        )
        saved = await save_artifact(
            session,
            workspace_id=row.workspace_id,
            thread_id=site.get("thread_id") or row.thread_id,
            tool_call_id=site.get("tool_call_id"),
            title=title,
            markdown_representation=f"# {title}\n\n{outline}\n",
            files=files,
            extra_metadata={
                "legacy": {"kind": "video", "id": row.id},
                "slide_count": len(slides),
                "scene_code_count": len(scene_codes),
                "slides": remotion_slides,
                "scene_codes": scene_codes,
            },
            format=ArtifactFormat.VIDEO,
        )
        return saved.artifact_id

    async with async_session_maker() as session:
        rows = await _pending_rows(session)
        artifacts = await _already_converted(session)
        sites = await _call_sites(session)
        pending = [row for row in rows if row.id not in artifacts]

        # READY rows with a NULL column whose Artifact already exists (live path
        # before the column landed): stamp the link, don't re-create.
        strays = [row for row in rows if row.id in artifacts]

        print(f"{len(rows)} pending video row(s); {len(artifacts)} already converted.")
        if not apply:
            print(f"Dry run: {len(pending)} row(s) would become Artifacts.")
            if strays:
                print(f"{len(strays)} row(s) would just get their artifact_id stamped.")
            print("Re-run with --yes to convert them.")
            return

        for row in strays:
            await session.execute(
                text(
                    "UPDATE video_presentations SET artifact_id = :aid WHERE id = :id"
                ),
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
                    text(
                        "UPDATE video_presentations "
                        "SET artifact_id = :aid WHERE id = :id"
                    ),
                    {"aid": artifact_id, "id": row.id},
                )
                await session.commit()
                artifacts[row.id] = (artifact_id, row.workspace_id)
            except Exception as exc:
                await session.rollback()
                failed += 1
                print(f"  video {row.id}: FAILED ({exc})")

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
