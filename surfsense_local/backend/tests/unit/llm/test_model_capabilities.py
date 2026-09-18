import pytest
from pydantic import ValidationError

from modules.llm.connections.model_capabilities import (
    ModelCapabilitiesManifest,
    load_model_capabilities,
    lookup_capabilities,
)

pytestmark = pytest.mark.unit


def test_packaged_catalogue_classifies_the_models_openai_publishes() -> None:
    """The shipped table parses, and answers the ids /models actually returns."""
    manifest = load_model_capabilities()

    assert manifest.schema_version == 1
    # OpenRouter declares on the wire, so its rows would never be reached.
    assert manifest.excluded_providers == ["openrouter"]
    assert manifest.models

    assert all(row.origin == "models.dev" for row in manifest.models.values())

    assert lookup_capabilities("gpt-4o") == ("completion",)
    assert lookup_capabilities("gpt-image-2") == ("image_generation",)
    # Speech, transcription and video are exact, because a model that does not
    # take text in and give text out cannot hold a chat whatever it is called.
    assert lookup_capabilities("whisper-large-v3") == ()
    assert lookup_capabilities("voxtral-mini-tts-latest") == ()
    assert lookup_capabilities("veo-3.1-generate-preview") == ()


def test_lookup_falls_back_to_the_last_path_segment() -> None:
    """Gemini prefixes ids with models/ and gateways with a vendor name."""
    assert lookup_capabilities("models/gpt-4o") == ("completion",)
    assert lookup_capabilities("openai/gpt-4o") == ("completion",)


def test_lookup_separates_not_listed_from_known_to_be_neither() -> None:
    """None means no row; an empty tuple means a row saying it does neither."""
    assert lookup_capabilities("a-model-nobody-has-catalogued") is None
    assert lookup_capabilities("whisper-large-v3") == ()


def test_models_openai_serves_but_modelsdev_omits_are_left_unknown() -> None:
    """The bug this replaced: these used to be read off the name as chat.

    models.dev tracks models people build agents on, so OpenAI's legacy and
    single-purpose ids are simply absent. Absent has to mean unknown, because
    the alternative is the guess that reported babbage-002 as a chat model.
    """
    for name in (
        "babbage-002",
        "davinci-002",
        "computer-use-preview",
        "tts-1",
        "whisper-1",
    ):
        assert lookup_capabilities(name) is None


def test_embedding_models_are_a_known_and_accepted_gap() -> None:
    """models.dev has no modality for a vector, so these read as text-to-text.

    Asserted so the cost of taking models.dev verbatim is visible in the suite
    rather than discovered in the picker. If a future models.dev can express it,
    this test fails and the limitation is gone.
    """
    assert lookup_capabilities("text-embedding-3-small") == ("completion",)


def test_manifest_rejects_a_capability_the_app_has_no_role_for() -> None:
    """A typo in a hand-written row fails loudly instead of disabling a button."""
    with pytest.raises(ValidationError, match="unknown capability"):
        ModelCapabilitiesManifest.model_validate(
            {
                "schema_version": 1,
                "source": "https://models.dev/api.json",
                "excluded_providers": ["openrouter"],
                "models": {
                    "gpt-4o": {"capabilities": ["embedding"], "origin": "curated"}
                },
            }
        )


def test_manifest_rejects_an_unsupported_schema_version() -> None:
    """A regenerated file from a newer script must not be read as if it were v1."""
    with pytest.raises(ValidationError, match="unsupported model-capability schema"):
        ModelCapabilitiesManifest.model_validate(
            {
                "schema_version": 2,
                "source": "https://models.dev/api.json",
                "excluded_providers": ["openrouter"],
                "models": {},
            }
        )
