"""Entrypoint for SERVICE_ROLE=gateway."""

from __future__ import annotations

import asyncio

from app.gateway.runner import GatewayRunner

if __name__ == "__main__":
    asyncio.run(GatewayRunner().run())

