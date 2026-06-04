"""Client for ``/api/v1/searchspaces`` and ``/api/v1/search-spaces/{id}/llm-preferences``.

Verified against:

* ``surfsense_backend/app/routes/search_spaces_routes.py:116`` (POST create)
* ``surfsense_backend/app/routes/search_spaces_routes.py:234`` (GET by id)
* ``surfsense_backend/app/routes/search_spaces_routes.py:422`` (DELETE soft-delete)
* ``surfsense_backend/app/routes/search_spaces_routes.py:698-849`` (GET/PUT llm-preferences)
* ``surfsense_backend/app/schemas/search_space.py:14`` (SearchSpaceCreate body)
* ``surfsense_backend/app/routes/vision_llm_routes.py:60`` (GET global vision configs)

Note the inconsistent pluralisation in the backend: ``/searchspaces``
(no hyphen) for CRUD, but ``/search-spaces`` (hyphenated) for the
``llm-preferences`` sub-resource. Both are mirrored verbatim here.
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
class VisionLlmConfigEntry:
    """Subset of one ``GET /global-vision-llm-configs`` row.

    The backend returns negative ids for global / OpenRouter-derived
    vision configs and positive ids for per-user BYOK rows. Either is
    accepted by ``set_llm_preferences(vision_llm_config_id=...)``.
    """

    id: int
    name: str
    provider: str
    model_name: str
    is_auto_mode: bool
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> VisionLlmConfigEntry:
        return cls(
            id=int(payload.get("id", 0)),
            name=str(payload.get("name", "")),
            provider=str(payload.get("provider", "")).upper(),
            model_name=str(payload.get("model_name", "")),
            is_auto_mode=bool(payload.get("is_auto_mode", False)),
            raw=payload,
        )


@dataclass
class LlmPreferences:
    """Resolved LLM preferences with the embedded full config row.

    Mirrors ``LLMPreferencesRead`` from the backend so the lifecycle
    command can introspect ``provider`` / ``model_name`` to validate the
    OpenRouter pin.
    """

    agent_llm_id: int | None
    image_generation_config_id: int | None
    vision_llm_config_id: int | None
    agent_llm: dict[str, Any] | None
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> LlmPreferences:
        return cls(
            agent_llm_id=payload.get("agent_llm_id"),
            image_generation_config_id=payload.get("image_generation_config_id"),
            vision_llm_config_id=payload.get("vision_llm_config_id"),
            agent_llm=payload.get("agent_llm"),
            raw=payload,
        )


class SearchSpaceClient:
    """Thin wrapper around the SearchSpace + LLM preferences endpoints."""

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

    async def get_llm_preferences(self, search_space_id: int) -> LlmPreferences:
        response = await self._http.get(
            f"{self._base}/api/v1/search-spaces/{search_space_id}/llm-preferences",
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return LlmPreferences.from_payload(response.json())

    async def set_llm_preferences(
        self,
        search_space_id: int,
        *,
        agent_llm_id: int | None = None,
        image_generation_config_id: int | None = None,
        vision_llm_config_id: int | None = None,
    ) -> LlmPreferences:
        """PUT a partial update to ``/search-spaces/{id}/llm-preferences``.

        Backend uses ``model_dump(exclude_unset=True)`` so omitted fields
        are left unchanged.
        """

        body: dict[str, Any] = {}
        if agent_llm_id is not None:
            body["agent_llm_id"] = agent_llm_id
        if image_generation_config_id is not None:
            body["image_generation_config_id"] = image_generation_config_id
        if vision_llm_config_id is not None:
            body["vision_llm_config_id"] = vision_llm_config_id
        response = await self._http.put(
            f"{self._base}/api/v1/search-spaces/{search_space_id}/llm-preferences",
            json=body,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return LlmPreferences.from_payload(response.json())

    async def list_global_vision_llm_configs(self) -> list[VisionLlmConfigEntry]:
        """List the registered global vision LLM configs.

        Used by ``setup`` to (a) resolve an explicit ``--vision-llm <slug>``
        to a config id and (b) auto-pick the strongest registered vision
        config when the operator doesn't pass one. The ``Auto (Fastest)``
        entry (``id=0``) is filtered out — accuracy must be reproducible.
        """

        response = await self._http.get(
            f"{self._base}/api/v1/global-vision-llm-configs",
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError(
                f"Unexpected /global-vision-llm-configs payload: {payload!r}"
            )
        return [
            VisionLlmConfigEntry.from_payload(item)
            for item in payload
            if not bool(item.get("is_auto_mode", False))
        ]
