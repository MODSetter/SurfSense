"""Driving an install job to its end, as the screens follow one."""

import asyncio

from httpx import AsyncClient

ENDED = {"complete", "error", "cancelled"}


async def wait_for_end(client: AsyncClient, job_id: str) -> dict:
    """The job once its last event arrives."""
    for _ in range(500):
        job = (await client.get(f"/llm/installs/{job_id}")).json()
        if job["event"]["type"] in ENDED:
            return job
        await asyncio.sleep(0.01)
    raise AssertionError(f"install {job_id} did not end")


async def install_to_end(client: AsyncClient, **body: object) -> dict:
    """Start one install and return its job once it ends."""
    started = await client.post("/llm/installs", json=body)
    assert started.status_code == 202, started.text
    return await wait_for_end(client, started.json()["id"])
