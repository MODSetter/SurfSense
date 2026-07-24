import asyncio
import threading

import pytest

from app.utils.file_io import write_bytes

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_write_bytes_does_not_block_event_loop(monkeypatch, tmp_path):
    write_started = threading.Event()
    release_write = threading.Event()

    def blocking_write(_path, _content):
        write_started.set()
        release_write.wait(timeout=1)
        return 5

    monkeypatch.setattr("pathlib.Path.write_bytes", blocking_write)

    task = asyncio.create_task(write_bytes(str(tmp_path / "audio.mp3"), b"audio"))
    while not write_started.is_set():
        await asyncio.sleep(0)

    assert not task.done()
    release_write.set()
    await task
