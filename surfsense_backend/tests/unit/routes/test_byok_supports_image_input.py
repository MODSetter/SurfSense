"""Unit tests for ``supports_image_input`` derivation on BYOK chat config
endpoints (``GET /new-llm-configs`` list, ``GET /new-llm-configs/{id}``).

There is no DB column for ``supports_image_input`` on
``NewLLMConfig`` — the value is resolved at the API boundary by
``derive_supports_image_input`` so the new-chat selector / streaming
task can read the same field shape regardless of source (BYOK vs YAML
vs OpenRouter dynamic). Default-allow on unknown so we don't lock the
user out of their own model choice.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db import LiteLLMProvider
from app.routes import new_llm_config_routes

pytestmark = pytest.mark.unit


def _byok_row(
    *,
    id_: int,
    model_name: str,
    base_model: str | None = None,
    provider: LiteLLMProvider = LiteLLMProvider.OPENAI,
    custom_provider: str | None = None,
) -> object:
    """Mimic the SQLAlchemy row's attribute surface; ``model_validate``
    walks ``from_attributes=True`` so a ``SimpleNamespace`` is enough.

    ``provider`` is a real ``LiteLLMProvider`` enum value so Pydantic's
    enum validator accepts it — same as the ORM row would carry."""
    return SimpleNamespace(
        id=id_,
        name=f"BYOK-{id_}",
        description=None,
        provider=provider,
        custom_provider=custom_provider,
        model_name=model_name,
        api_key="sk-byok",
        api_base=None,
        litellm_params={"base_model": base_model} if base_model else None,
        system_instructions="",
        use_default_system_instructions=True,
        citations_enabled=True,
        created_at=datetime.now(tz=UTC),
        search_space_id=42,
        user_id=uuid4(),
    )


def test_serialize_byok_known_vision_model_resolves_true():
    """The catalog resolver consults LiteLLM's map for ``gpt-4o`` ->
    True. The serialized row carries that value through to the
    ``NewLLMConfigRead`` schema."""
    row = _byok_row(id_=1, model_name="gpt-4o")
    serialized = new_llm_config_routes._serialize_byok_config(row)

    assert serialized.supports_image_input is True
    assert serialized.id == 1
    assert serialized.model_name == "gpt-4o"


def test_serialize_byok_unknown_model_default_allows():
    """Unknown / unmapped: default-allow. The streaming-task safety net
    is the actual block, and it requires LiteLLM to *explicitly* say
    text-only — so a brand new BYOK model should not be pre-judged."""
    row = _byok_row(
        id_=2,
        model_name="brand-new-model-x9-unmapped",
        provider=LiteLLMProvider.CUSTOM,
        custom_provider="brand_new_proxy",
    )
    serialized = new_llm_config_routes._serialize_byok_config(row)

    assert serialized.supports_image_input is True


def test_serialize_byok_uses_base_model_when_present():
    """Azure-style: ``model_name`` is the deployment id, ``base_model``
    inside ``litellm_params`` is the canonical sku LiteLLM knows. The
    helper must consult ``base_model`` first or unrecognised deployment
    ids would shadow the real capability."""
    row = _byok_row(
        id_=3,
        model_name="my-azure-deployment-id-no-litellm-knows-this",
        base_model="gpt-4o",
        provider=LiteLLMProvider.AZURE_OPENAI,
    )
    serialized = new_llm_config_routes._serialize_byok_config(row)

    assert serialized.supports_image_input is True


def test_serialize_byok_returns_pydantic_read_model():
    """The route now returns ``NewLLMConfigRead`` (not the raw ORM) so
    the schema additions are guaranteed to be present in the API
    surface. This guards against a future regression where someone
    deletes the augmentation step and falls back to ORM passthrough."""
    from app.schemas import NewLLMConfigRead

    row = _byok_row(id_=4, model_name="gpt-4o")
    serialized = new_llm_config_routes._serialize_byok_config(row)
    assert isinstance(serialized, NewLLMConfigRead)
