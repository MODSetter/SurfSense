"""Bounded sandbox file reads for providers without a streaming file API."""

from __future__ import annotations

import base64
import shlex
from collections.abc import AsyncIterator, Awaitable, Callable

from .protocol import ExecResult

DEFAULT_FILE_CHUNK_SIZE = 1024 * 1024


async def read_file_stream_via_commands(
    run_command: Callable[[str], Awaitable[ExecResult]],
    path: str,
    *,
    chunk_size: int = DEFAULT_FILE_CHUNK_SIZE,
) -> AsyncIterator[bytes]:
    """Read a file in bounded chunks through the provider's command channel."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    quoted_path = shlex.quote(path)
    index = 0
    while True:
        pipeline = (
            f"dd if={quoted_path} bs={chunk_size} skip={index} count=1 "
            "status=none | base64 -w0"
        )
        result = await run_command(f"bash -o pipefail -c {shlex.quote(pipeline)}")
        if not result.ok:
            raise RuntimeError(f"Sandbox stream read failed for {path}")
        if result.truncated:
            raise RuntimeError(f"Sandbox stream read was truncated for {path}")
        try:
            chunk = base64.b64decode(result.output.strip(), validate=True)
        except ValueError as exc:
            raise RuntimeError(
                f"Sandbox returned an invalid file chunk for {path}"
            ) from exc
        if not chunk:
            return
        yield chunk
        if len(chunk) < chunk_size:
            return
        index += 1
