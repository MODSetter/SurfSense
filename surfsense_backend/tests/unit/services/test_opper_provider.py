"""Unit tests for the Opper provider spec.

Opper (https://opper.ai) is an EU-hosted OpenAI-compatible gateway. Its
``/v3/compat/models`` endpoint returns the plain OpenAI shape, so it uses the
generic ``openai_models`` discovery rather than a dedicated normalizer like
OpenRouter and Requesty need.

The base URL is the one case worth pinning: it ends in ``/v3/compat`` rather
than ``/v1``, and discovery appends ``/models`` verbatim, so the resulting URL
must be ``https://api.opper.ai/v3/compat/models``.
"""

from __future__ import annotations

import pytest

from app.services.provider_registry import REGISTRY, Transport, spec_for

pytestmark = pytest.mark.unit


def test_opper_is_registered():
    assert "opper" in REGISTRY


def test_opper_spec_fields():
    spec = spec_for("opper")
    assert spec.transport is Transport.OPENAI_COMPATIBLE
    assert spec.litellm_prefix == "openai"
    assert spec.discovery == "openai_models"
    assert spec.default_base_url == "https://api.opper.ai/v3/compat"
    assert spec.base_url_required is False
    assert spec.auth_style == "bearer"
    assert spec.display_name == "Opper"


def test_opper_discovery_url_keeps_the_compat_path():
    """Discovery appends /models verbatim; Opper's base is not a /v1 root."""
    base_url = spec_for("opper").default_base_url
    assert f"{base_url.rstrip('/')}/models" == "https://api.opper.ai/v3/compat/models"
