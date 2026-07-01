"""SearXNG discover provider, wrapping the platform-env SearXNG search service."""

from __future__ import annotations

from app.capabilities.web.discover.schemas import DiscoverHit
from app.services import web_search_service


class SearxngProvider:
    """Env-keyed via ``SEARXNG_DEFAULT_HOST`` (the platform SearXNG instance)."""

    name = "searxng"

    def is_available(self) -> bool:
        return web_search_service.is_available()

    async def search(self, query: str, top_k: int) -> list[DiscoverHit]:
        result_object, _documents = await web_search_service.search(query, top_k)
        return [
            DiscoverHit(
                url=source["url"],
                title=source.get("title") or source["url"],
                snippet=source.get("description") or None,
                provider=self.name,
            )
            for source in result_object.get("sources", [])
            if source.get("url")
        ]
