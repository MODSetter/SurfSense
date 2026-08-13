"""One-shot cutover: turn ``image_generations`` rows into Artifacts.

Run with --yes after deploying the artifact-only image code and before the
migration that drops ``image_generations``. Safe to re-run: rows that already
produced an Artifact are skipped.

Moves the image bytes into an ``ArtifactFile``, the generation parameters into
``artifact_metadata``, and repoints the ``generate_image`` payloads held by chat
messages and public snapshots from the deleted token URL to the Artifact.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
from typing import Any

from sqlalchemy import text

from app.db import async_session_maker
from app.file_storage.factory import get_storage_backend

PROVENANCE_COLUMNS = (
    "model",
    "n",
    "quality",
    "size",
    "style",
    "response_format",
    "image_gen_model_id",
)


async def _already_converted(session) -> dict[int, tuple[int, int]]:
    """Legacy image id → (artifact id, workspace id), from an earlier run."""
    result = await session.execute(
        text(
            """
            SELECT (metadata -> 'legacy' ->> 'id')::int AS legacy_id,
                   id, workspace_id
            FROM artifacts
            WHERE format = 'image'
              AND metadata -> 'legacy' ->> 'kind' = 'image'
            """
        )
    )
    return {row.legacy_id: (row.id, row.workspace_id) for row in result}


async def _pending_rows(session) -> list[Any]:
    result = await session.execute(
        text(
            """
            SELECT id, workspace_id, prompt, response_data, created_at,
                   created_by_id, model, n, quality, size, style,
                   response_format, image_gen_model_id
            FROM image_generations
            WHERE response_data IS NOT NULL
            ORDER BY id
            """
        )
    )
    return list(result)


def _tool_parts(content: Any):
    """Every ``generate_image`` tool-call part in a message content list."""
    if not isinstance(content, list):
        return
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "tool-call":
            continue
        if part.get("toolName") != "generate_image":
            continue
        if isinstance(part.get("result"), dict):
            yield part


async def _call_sites(session) -> dict[int, dict[str, Any]]:
    """Where each image was generated: thread and tool call, by legacy id."""
    result = await session.execute(
        text("SELECT id, thread_id, content FROM new_chat_messages")
    )
    sites: dict[int, dict[str, Any]] = {}
    for row in result:
        for part in _tool_parts(row.content):
            legacy_id = part["result"].get("image_generation_id")
            if isinstance(legacy_id, int) and legacy_id not in sites:
                sites[legacy_id] = {
                    "thread_id": row.thread_id,
                    "tool_call_id": part.get("toolCallId"),
                }
    return sites


async def _response_with_bytes(response_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a stored payload so the record path can read the image.

    Rows written before the artifact cutover hold the provider payload
    verbatim; rows written during it hold an object-store key instead.
    """
    entries = response_data.get("data")
    if not isinstance(entries, list) or not entries:
        raise ValueError("no data entries")
    entry = dict(entries[0])

    key = entry.pop("storage_key", None)
    if key and not entry.get("b64_json"):
        backend = get_storage_backend(entry.get("storage_backend"))
        chunks = [chunk async for chunk in backend.open_stream(key)]
        entry["b64_json"] = base64.b64encode(b"".join(chunks)).decode()
    entry.pop("storage_backend", None)

    return {"data": [entry]}


def _repoint(result: dict[str, Any], artifact_id: int, workspace_id: int):
    """Rewrite a stored tool payload onto the Artifact."""
    payload = {
        **result,
        "id": f"image-artifact-{artifact_id}",
        "artifact_id": artifact_id,
        "workspace_id": workspace_id,
    }
    for dead in ("src", "assetId", "image_generation_id", "image_count"):
        payload.pop(dead, None)
    return payload


async def _repoint_messages(session, artifacts: dict[int, tuple[int, int]]) -> int:
    result = await session.execute(text("SELECT id, content FROM new_chat_messages"))
    rows = [(row.id, row.content) for row in result]

    updated = 0
    for message_id, content in rows:
        touched = False
        for part in _tool_parts(content):
            legacy_id = part["result"].get("image_generation_id")
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
                legacy_id = part["result"].get("image_generation_id")
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
    from app.artifacts.media.image.record import record as record_image

    async with async_session_maker() as session:
        rows = await _pending_rows(session)
        artifacts = await _already_converted(session)
        sites = await _call_sites(session)
        pending = [row for row in rows if row.id not in artifacts]

        print(f"{len(rows)} image row(s); {len(artifacts)} already converted.")
        if not apply:
            print(f"Dry run: {len(pending)} row(s) would become Artifacts.")
            print("Re-run with --yes to convert them.")
            return

        failed = 0
        for row in pending:
            site = sites.get(row.id, {})
            try:
                response = await _response_with_bytes(row.response_data)
                saved = await record_image(
                    session,
                    workspace_id=row.workspace_id,
                    prompt=row.prompt or "Generated image",
                    response=response,
                    provenance={
                        "legacy": {"kind": "image", "id": row.id},
                        "generated_at": row.created_at.isoformat()
                        if row.created_at
                        else None,
                        "generated_by_id": str(row.created_by_id)
                        if row.created_by_id
                        else None,
                        **{
                            column: getattr(row, column)
                            for column in PROVENANCE_COLUMNS
                        },
                    },
                    thread_id=site.get("thread_id"),
                    tool_call_id=site.get("tool_call_id"),
                )
                await session.commit()
                artifacts[row.id] = (saved.artifact_id, row.workspace_id)
            except Exception as exc:
                await session.rollback()
                failed += 1
                print(f"  image {row.id}: FAILED ({exc})")

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
