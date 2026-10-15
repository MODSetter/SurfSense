"""Which model and provider a live run calls, chosen from the environment."""

import pytest

from tests.live.live_model import chosen_model, chosen_provider
from tests.live.model_prices import ANTHROPIC_PRICES, Prices
from tests.live.openrouter_stand_in import serve_listing

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test states its own choice."""
    monkeypatch.delenv("SURFSENSE_LIVE_MODEL", raising=False)
    monkeypatch.delenv("SURFSENSE_LIVE_PROVIDER", raising=False)


def test_runs_stay_on_sonnet_through_anthropic_unless_told_otherwise() -> None:
    """Today's runs are unchanged."""
    model = chosen_model()

    assert model.name == "claude-sonnet-5-5"
    assert model.provider.name == "anthropic"
    assert model.provider.key_env == "ANTHROPIC_API_KEY"
    assert model.provider.catalog_provider == "anthropic"
    assert model.upstream == "https://api.anthropic.com/v1"
    assert model.prices == ANTHROPIC_PRICES["claude-sonnet-5-5"]
    assert model.label == "anthropic/claude-sonnet-5-5"


def test_another_claude_model_is_priced_at_its_own_rates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ladder rung below Sonnet is charged as itself."""
    monkeypatch.setenv("SURFSENSE_LIVE_MODEL", "claude-haiku-4-5")

    model = chosen_model()

    assert model.name == "claude-haiku-4-5"
    assert model.prices == ANTHROPIC_PRICES["claude-haiku-4-5"]
    assert model.reads_images is True


def test_a_claude_model_without_a_price_stops_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ledger cannot charge a model it has no prices for."""
    monkeypatch.setenv("SURFSENSE_LIVE_MODEL", "claude-unpriced-9")

    with pytest.raises(ValueError, match="claude-unpriced-9"):
        chosen_model()


def test_openrouter_is_connected_as_the_app_connects_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its catalog entry, so the app reads the model's row and declares its image input."""
    monkeypatch.setenv("SURFSENSE_LIVE_PROVIDER", "openrouter")
    monkeypatch.setenv("SURFSENSE_LIVE_MODEL", "anthropic/claude-haiku-4.5")
    listed = {"prompt": "0.000001", "completion": "0.000005"}

    with serve_listing(
        [{"id": "anthropic/claude-haiku-4.5", "pricing": listed}]
    ) as url:
        model = chosen_model(openrouter_listing=url)

    assert model.provider.key_env == "OPENROUTER_API_KEY"
    assert model.provider.catalog_provider == "openrouter"
    assert model.upstream == "https://openrouter.ai/api/v1"
    assert model.reads_images is True
    assert model.prices == Prices(
        input=1.0, output=5.0, cache_read=1.0, cache_write=1.0
    )
    assert model.label == "openrouter/anthropic/claude-haiku-4.5"


def test_a_model_the_manifest_does_not_carry_reads_no_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """As in the app: an id nothing vouches for is sent no images."""
    monkeypatch.setenv("SURFSENSE_LIVE_PROVIDER", "openrouter")
    monkeypatch.setenv("SURFSENSE_LIVE_MODEL", "nobody/unlisted-model")
    listed = {"prompt": "0.000001", "completion": "0.000005"}

    with serve_listing([{"id": "nobody/unlisted-model", "pricing": listed}]) as url:
        model = chosen_model(openrouter_listing=url)

    assert model.reads_images is False


def test_an_unknown_provider_names_the_ones_there_are(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo stops the run instead of falling back to Anthropic."""
    monkeypatch.setenv("SURFSENSE_LIVE_PROVIDER", "bedrock")

    with pytest.raises(ValueError, match="anthropic, openrouter"):
        chosen_provider()
