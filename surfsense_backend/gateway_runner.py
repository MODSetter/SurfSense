"""Entrypoint for SERVICE_ROLE=gateway."""

from __future__ import annotations

import asyncio
import logging

from app.gateway.runner import GatewayRunner

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(GatewayRunner().run())

