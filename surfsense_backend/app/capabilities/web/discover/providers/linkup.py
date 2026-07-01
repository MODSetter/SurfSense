"""Linkup discover provider (env-keyed via ``LINKUP_API_KEY``)."""

from __future__ import annotations

import asyncio

from linkup import LinkupClient

from app.capabilities.web.discover.schemas import DiscoverHit
from app.config import config


class LinkupProvider:
    name = "linkup"

    def is_available(self) -> bool:
        return bool(config.LINKUP_API_KEY)

    async def search(self, query: str, top_k: int) -> list[DiscoverHit]:
        client = LinkupClient(api_key=config.LINKUP_API_KEY)
        response = await asyncio.to_thread(
            client.search, query=query, depth="standard", output_type="searchResults"
        )
        hits: list[DiscoverHit] = []
        for result in getattr(response, "results", None) or []:
            url = getattr(result, "url", "") or ""
            if not url:
                continue
            content = getattr(result, "content", "") or ""
            hits.append(
                DiscoverHit(
                    url=url,
                    title=getattr(result, "name", "") or url,
                    snippet=content or None,
                    provider=self.name,
                )
            )
            if len(hits) >= top_k:
                break
        return hits
