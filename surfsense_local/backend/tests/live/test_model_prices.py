"""What each model a live run may use costs, per million tokens."""

import pytest

from tests.live.model_prices import ANTHROPIC_PRICES, Prices, openrouter_prices
from tests.live.openrouter_stand_in import serve_listing
from tests.live.spend_ledger import Usage

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("model", "input_", "output", "cache_read", "cache_write"),
    [
        # platform.claude.com/docs/en/about-claude/pricing, read 4 Oct 2026; 5-minute cache writes.
        ("claude-sonnet-5-5", 2.00, 10.00, 0.20, 2.50),
        ("claude-opus-5-5", 4.00, 20.00, 0.20, 5.00),
        ("claude-haiku-4-5", 1.00, 5.00, 0.10, 1.25),
    ],
)
def test_claude_is_priced_at_anthropics_published_rates(
    model: str, input_: float, output: float, cache_read: float, cache_write: float
) -> None:
    """Input, output, cache read and cache write, per million tokens."""
    prices = ANTHROPIC_PRICES[model]

    assert prices.dollars(Usage(input_tokens=1_000_000)) == pytest.approx(input_)
    assert prices.dollars(Usage(output_tokens=1_000_000)) == pytest.approx(output)
    assert prices.dollars(Usage(cache_read_tokens=1_000_000)) == pytest.approx(
        cache_read
    )
    assert prices.dollars(Usage(cache_write_tokens=1_000_000)) == pytest.approx(
        cache_write
    )


LISTING = [
    {
        "id": "anthropic/claude-haiku-4.5",
        "pricing": {
            "prompt": "0.000001",
            "completion": "0.000005",
            "input_cache_read": "0.0000001",
            "input_cache_write": "0.00000125",
        },
    },
    {
        "id": "qwen/qwen3-235b-a22b",
        "pricing": {"prompt": "0.000000455", "completion": "0.00000182"},
    },
]


def test_an_openrouter_model_is_priced_from_its_listing_per_token() -> None:
    """OpenRouter lists dollars per token; the ledger counts per million."""
    with serve_listing(LISTING) as url:
        prices = openrouter_prices("anthropic/claude-haiku-4.5", url)

    assert prices == Prices(input=1.00, output=5.00, cache_read=0.10, cache_write=1.25)


def test_a_model_listed_without_cache_prices_bills_cached_tokens_as_input() -> None:
    """No cache price means no discount to count on; input is the safe rate."""
    with serve_listing(LISTING) as url:
        prices = openrouter_prices("qwen/qwen3-235b-a22b", url)

    assert prices.cache_read == pytest.approx(0.455)
    assert prices.cache_write == pytest.approx(0.455)
    assert prices.output == pytest.approx(1.82)


def test_a_model_openrouter_does_not_list_stops_the_run() -> None:
    """Without a price the stop cannot hold."""
    with serve_listing(LISTING) as url, pytest.raises(ValueError, match="not-a/model"):
        openrouter_prices("not-a/model", url)


def test_the_worst_case_prompt_is_counted_at_the_dearer_input_rate() -> None:
    """A prompt may be written to the cache or not; the stop assumes the dearer."""
    cache_dearer = Prices(input=1.0, output=5.0, cache_read=0.1, cache_write=1.25)
    input_dearer = Prices(input=1.0, output=5.0, cache_read=0.1, cache_write=0.5)

    assert cache_dearer.dearest_prompt(10) == Usage(cache_write_tokens=10)
    assert input_dearer.dearest_prompt(10) == Usage(input_tokens=10)
