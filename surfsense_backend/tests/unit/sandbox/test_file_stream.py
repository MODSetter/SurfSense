import base64

import pytest

from app.sandbox.file_stream import read_file_stream_via_commands
from app.sandbox.protocol import ExecResult


async def test_command_file_stream_reads_bounded_chunks():
    payload = b"abcdefghij"
    calls = 0

    async def run(command):
        nonlocal calls
        assert "bs=4" in command
        start = calls * 4
        calls += 1
        return ExecResult(base64.b64encode(payload[start : start + 4]).decode(), 0)

    chunks = [
        chunk
        async for chunk in read_file_stream_via_commands(
            run, "/workspace/out.mp4", chunk_size=4
        )
    ]

    assert chunks == [b"abcd", b"efgh", b"ij"]
    assert b"".join(chunks) == payload


async def test_command_file_stream_propagates_pipeline_failure():
    async def run(command):
        assert "pipefail" in command
        return ExecResult("dd: file not found", 1)

    with pytest.raises(RuntimeError, match="stream read failed"):
        async for _ in read_file_stream_via_commands(run, "/workspace/missing.mp4"):
            pass
