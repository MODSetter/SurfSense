import asyncio
from pathlib import Path


async def write_bytes(path: str, content: bytes) -> None:
    """Write bytes without blocking the event loop."""
    await asyncio.to_thread(Path(path).write_bytes, content)
