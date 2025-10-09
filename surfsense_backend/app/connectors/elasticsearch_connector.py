from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from elasticsearch import AsyncElasticsearch


class ElasticsearchConnector:
    """Async helper for executing Elasticsearch searches."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._client: AsyncElasticsearch | None = None

    async def __aenter__(self) -> ElasticsearchConnector:
        self._client = AsyncElasticsearch(**self._build_client_kwargs())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _build_client_kwargs(self) -> dict[str, Any]:
        hostname = self._config.get("hostname")
        if not hostname:
            raise ValueError("Elasticsearch connector config missing 'hostname'.")

        port = int(self._config.get("port", 9200))
        ssl_enabled = bool(self._config.get("ssl_enabled", True))
        scheme = "https" if ssl_enabled else "http"

        kwargs: dict[str, Any] = {
            "hosts": [{"host": hostname, "port": port, "scheme": scheme}],
            "verify_certs": ssl_enabled,
        }

        auth_method = self._config.get("auth_method", "api_key")
        if auth_method == "api_key":
            api_key = self._config.get("ELASTICSEARCH_API_KEY")
            if not api_key:
                raise ValueError(
                    "Elasticsearch connector config missing 'ELASTICSEARCH_API_KEY'."
                )
            kwargs["api_key"] = api_key
        elif auth_method == "basic":
            username = self._config.get("username")
            password = self._config.get("password")
            if not username or not password:
                raise ValueError(
                    "Elasticsearch basic auth requires 'username' and 'password'."
                )
            kwargs["basic_auth"] = (username, password)
        else:
            raise ValueError(f"Unsupported Elasticsearch auth method '{auth_method}'.")

        if not ssl_enabled:
            kwargs["verify_certs"] = False
            kwargs["ssl_show_warn"] = False

        return kwargs

    async def search_documents(
        self,
        *,
        indices: Iterable[str] | None,
        query: str,
        search_fields: Iterable[str] | None,
        max_documents: int,
    ) -> list[dict[str, Any]]:
        if self._client is None:
            raise RuntimeError(
                "Elasticsearch client not initialised. Use as an async context manager."
            )

        size = max(1, min(int(max_documents or 1000), 10_000))
        index_param = ",".join(indices) if indices else None

        if not query or query == "*":
            query_body: dict[str, Any] = {"match_all": {}}
        else:
            query_body = {"query_string": {"query": query}}
            if search_fields:
                fields = [field for field in search_fields if field]
                if fields:
                    query_body["query_string"]["fields"] = fields

        response = await self._client.search(
            index=index_param,
            size=size,
            query=query_body,
            _source_includes=list(search_fields) if search_fields else None,
        )
        return response.get("hits", {}).get("hits", [])
