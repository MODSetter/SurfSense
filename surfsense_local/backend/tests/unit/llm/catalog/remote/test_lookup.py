"""Which manifest entry describes a model a connection lists, and what it is."""

import pytest

from modules.llm.catalog.remote.manifest.lookup import RemoteLookup
from modules.llm.catalog.remote.manifest.schema import RemoteManifest
from modules.llm.model_type import ModelType

pytestmark = pytest.mark.unit

CHAT = ({"input": ["text"], "output": ["text"]}, 400000)
PAINTER = ({"input": ["text", "image"], "output": ["text", "image"]}, 400000)
EMBEDDER = ({"input": ["text"], "output": ["text"]}, 8191)


def _model(shape: tuple[dict, int]) -> dict:
    modalities, context = shape
    return {
        "name": "model",
        "family": None,
        "description": None,
        "release_date": None,
        "status": None,
        "modalities": modalities,
        "context": context,
        "output_limit": None,
        "tool_call": True,
        "reasoning": False,
        "reasoning_options": None,
        "structured_output": None,
        "temperature": None,
    }


def _lookup(providers: dict[str, dict[str, tuple[dict, int]]]) -> RemoteLookup:
    return RemoteLookup(
        RemoteManifest.model_validate(
            {
                "schema_version": 1,
                "source": "https://models.dev/api.json",
                "refreshed_at": "2026-09-23",
                "providers": {
                    provider: {
                        "name": provider,
                        "doc": None,
                        "models": {mid: _model(shape) for mid, shape in models.items()},
                    }
                    for provider, models in providers.items()
                },
            }
        )
    )


def test_a_connection_to_a_known_provider_reads_that_provider_only() -> None:
    """The same id means what the serving provider says it means."""
    lookup = _lookup({"kenari": {"gpt-5-5": CHAT}, "neon": {"gpt-5-5": PAINTER}})

    found = lookup.classify("gpt-5-5", provider="neon")

    assert found.known is True
    assert found.types == {
        ModelType.TEXT_GEN,
        ModelType.IMAGE_GEN,
        ModelType.IMAGE_EDIT,
    }


def test_the_maker_describes_its_own_model() -> None:
    """`openai/gpt-5.5` on a gateway is OpenAI's `gpt-5.5`, whatever a reseller adds."""
    lookup = _lookup(
        {"openai": {"gpt-5.5": CHAT}, "nano-gpt": {"openai/gpt-5.5": PAINTER}}
    )

    assert lookup.classify("openai/gpt-5.5").types == {ModelType.TEXT_GEN}


def test_without_a_maker_the_types_every_provider_agrees_on_are_kept() -> None:
    """One reseller adding image output does not make gpt-5-5 unknown, and does
    not make it an image model either."""
    lookup = _lookup({"kenari": {"gpt-5-5": CHAT}, "neon": {"gpt-5-5": PAINTER}})

    found = lookup.classify("gpt-5-5")

    assert (found.known, found.types) == (True, {ModelType.TEXT_GEN})


def test_an_id_is_tried_whole_then_by_its_last_segment() -> None:
    """Gemini answers `models/<id>` and gateways prefix a vendor."""
    lookup = _lookup({"google": {"gemini-3-flash": CHAT}})

    assert lookup.classify("models/gemini-3-flash").types == {ModelType.TEXT_GEN}


def test_a_provider_that_lacks_the_id_falls_back_to_every_provider() -> None:
    """A model newer than the manifest refresh is still worth a label."""
    lookup = _lookup({"openai": {}, "azure": {"gpt-7": CHAT}})

    assert lookup.classify("gpt-7", provider="openai").types == {ModelType.TEXT_GEN}


def test_an_embedder_is_known_to_fill_no_slot() -> None:
    """Known-none is an answer; it is not unknown."""
    lookup = _lookup({"openai": {"text-embedding-3-small": EMBEDDER}})

    found = lookup.classify("text-embedding-3-small")

    assert (found.known, found.types) == (True, frozenset())


def test_an_id_nothing_carries_is_unknown() -> None:
    """A fine-tune on a company vLLM is in no manifest, and nothing is guessed."""
    lookup = _lookup({"openai": {"gpt-5": CHAT}})

    found = lookup.classify("acme/llama-support-v2")

    assert (found.known, found.types, found.supports) == (False, frozenset(), None)
