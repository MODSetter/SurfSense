"""Wait for sd-server to serve a model: Electron starts it on its next poll
after a Studio job needs it, and a request before then finds nothing."""

import asyncio
import time

import httpx


class ImageServerNotReadyError(RuntimeError):
    """sd-server did not come up on the model a job needs."""


async def wait_until_serving(
    root_url: str,
    filename: str,
    *,
    timeout: float = 120.0,
    interval: float = 1.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    """Until `/sdapi/v1/sd-models` names `filename`, the weights sd-server was
    launched on; its OpenAI routes answer the same whatever model it holds."""
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=5.0, transport=transport) as client:
        while True:
            try:
                reply = await client.get(f"{root_url}/sdapi/v1/sd-models")
                if reply.status_code == 200 and any(
                    model.get("filename") == filename for model in reply.json()
                ):
                    return
            except (httpx.HTTPError, ValueError):
                pass
            if time.monotonic() >= deadline:
                raise ImageServerNotReadyError(
                    "The image model did not start. Try again, or restart SurfSense."
                )
            await asyncio.sleep(interval)
