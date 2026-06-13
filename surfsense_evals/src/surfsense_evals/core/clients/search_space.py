"""Client for ``/api/v1/searchspaces`` and model-role endpoints.

Verified against:

* ``surfsense_backend/app/routes/search_spaces_routes.py:116`` (POST create)
* ``surfsense_backend/app/routes/search_spaces_routes.py:234`` (GET by id)
* ``surfsense_backend/app/routes/search_spaces_routes.py:422`` (DELETE soft-delete)
* ``surfsense_backend/app/routes/model_connections_routes.py`` (GET/PUT model roles)
* ``surfsense_backend/app/schemas/search_space.py:14`` (SearchSpaceCreate body)

Note the inconsistent pluralisation in the backend: ``/searchspaces``
(no hyphen) for CRUD, but ``/search-spaces`` (hyphenated) for model-role
sub-resources. Both are mirrored verbatim here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class SearchSpaceRow:
    """Subset of the SearchSpace row we care about."""

    id: int
    name: str
    description: str | None
    user_id: str
    citations_enabled: bool
    qna_custom_instructions: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SearchSpaceRow:
        return cls(
            id=int(payload["id"]),
            name=str(payload["name"]),
            description=payload.get("description"),
            user_id=str(payload.get("user_id", "")),
            citations_enabled=bool(payload.get("citations_enabled", True)),
            qna_custom_instructions=payload.get("qna_custom_instructions"),
        )


@dataclass
class VisionModelEntry:
    """Subset of one GLOBAL model-connection model with image input support."""

    id: int
    name: str
    provider: str
    model_name: str
    is_auto_mode: bool
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> VisionModelEntry:
        return cls(
            id=int(payload.get("id", 0)),
            name=str(payload.get("display_name") or payload.get("model_id") or ""),
            provider=str(payload.get("provider", "")).upper(),
            model_name=str(payload.get("model_id", "")),
            is_auto_mode=False,
            raw=payload,
        )


@dataclass
class ModelRoles:
    """Model role ids for a search space."""

    chat_model_id: int | None
    image_gen_model_id: int | None
    vision_model_id: int | None
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ModelRoles:
        return cls(
            chat_model_id=payload.get("chat_model_id"),
            image_gen_model_id=payload.get("image_gen_model_id"),
            vision_model_id=payload.get("vision_model_id"),
            raw=payload,
        )


class SearchSpaceClient:
    """Thin wrapper around the SearchSpace + model role endpoints."""

    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    async def create(self, name: str, *, description: str | None = None) -> SearchSpaceRow:
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        # citations_enabled defaults to True backend-side; keep that default.
        response = await self._http.post(
            f"{self._base}/api/v1/searchspaces",
            json=body,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return SearchSpaceRow.from_payload(response.json())

    async def get(self, search_space_id: int) -> SearchSpaceRow:
        response = await self._http.get(
            f"{self._base}/api/v1/searchspaces/{search_space_id}",
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return SearchSpaceRow.from_payload(response.json())

    async def delete(self, search_space_id: int) -> None:
        """Soft-delete: backend prefixes name with ``[DELETING]`` and dispatches a Celery cascade."""

        response = await self._http.delete(
            f"{self._base}/api/v1/searchspaces/{search_space_id}",
            headers={"Accept": "application/json"},
        )
        # 404 means it's already gone — treat as success (idempotent teardown).
        if response.status_code == 404:
            return
        response.raise_for_status()

    async def get_model_roles(self, search_space_id: int) -> ModelRoles:
        response = await self._http.get(
            f"{self._base}/api/v1/search-spaces/{search_space_id}/model-roles",
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return ModelRoles.from_payload(response.json())

    async def set_model_roles(
        self,
        search_space_id: int,
        *,
        chat_model_id: int | None = None,
        image_gen_model_id: int | None = None,
        vision_model_id: int | None = None,
    ) -> ModelRoles:
        """PUT a partial update to ``/search-spaces/{id}/model-roles``.

        Backend uses ``model_dump(exclude_unset=True)`` so omitted fields
        are left unchanged.
        """

        body: dict[str, Any] = {}
        if chat_model_id is not None:
            body["chat_model_id"] = chat_model_id
        if image_gen_model_id is not None:
            body["image_gen_model_id"] = image_gen_model_id
        if vision_model_id is not None:
            body["vision_model_id"] = vision_model_id
        response = await self._http.put(
            f"{self._base}/api/v1/search-spaces/{search_space_id}/model-roles",
            json=body,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return ModelRoles.from_payload(response.json())

    async def list_global_vision_models(self) -> list[VisionModelEntry]:
        """List registered GLOBAL models that can accept image input.

        Used by ``setup`` to resolve ``--vision-llm <slug>`` or auto-pick a
        reproducible ingest-time vision model.
        """

        response = await self._http.get(
            f"{self._base}/api/v1/model-connections/global",
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError(
                f"Unexpected /model-connections/global payload: {payload!r}"
            )
        entries: list[VisionModelEntry] = []
        for connection in payload:
            provider = str(connection.get("provider", ""))
            for model in connection.get("models") or []:
                if not model.get("enabled", True) or not model.get("supports_image_input"):
                    continue
                entries.append(
                    VisionModelEntry.from_payload({**model, "provider": provider})
                )
        return entries
