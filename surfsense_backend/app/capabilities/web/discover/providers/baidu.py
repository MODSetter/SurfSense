"""Baidu AI Search discover provider (env-keyed via ``BAIDU_API_KEY``)."""

from __future__ import annotations

import httpx

from app.capabilities.web.discover.schemas import DiscoverHit
from app.config import config

_ENDPOINT = "https://qianfan.baidubce.com/v2/ai_search/chat/completions"
_SNIPPET_MAX = 300


class BaiduProvider:
    name = "baidu"

    def is_available(self) -> bool:
        return bool(config.BAIDU_API_KEY)

    async def search(self, query: str, top_k: int) -> list[DiscoverHit]:
        max_per_type = min(top_k, 20)
        payload = {
            "messages": [{"role": "user", "content": query}],
            "model": config.BAIDU_MODEL,
            "search_source": config.BAIDU_SEARCH_SOURCE,
            "resource_type_filter": [{"type": "web", "top_k": max_per_type}],
            "stream": False,
        }
        headers = {
            "X-Appbuilder-Authorization": f"Bearer {config.BAIDU_API_KEY}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(_ENDPOINT, headers=headers, json=payload)
            response.raise_for_status()

        hits: list[DiscoverHit] = []
        for reference in response.json().get("references", []):
            url = reference.get("url", "")
            if not url:
                continue
            content = reference.get("content", "") or ""
            hits.append(
                DiscoverHit(
                    url=url,
                    title=reference.get("title") or url,
                    snippet=content[:_SNIPPET_MAX] or None,
                    provider=self.name,
                )
            )
            if len(hits) >= top_k:
                break
        return hits
