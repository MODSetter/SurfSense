"""What the models a live run may call cost, in dollars per million tokens."""

from dataclasses import dataclass
from decimal import Decimal

import httpx

from tests.live.usage import Usage

# Public, no key; read once when a run starts, so a run is charged at that day's rates.
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"


@dataclass(frozen=True)
class Prices:
    """Dollars per million tokens; a cache write is the 5-minute one."""

    input: float
    output: float
    cache_read: float
    cache_write: float

    def dollars(self, usage: Usage) -> float:
        return (
            usage.input_tokens * self.input
            + usage.output_tokens * self.output
            + usage.cache_read_tokens * self.cache_read
            + usage.cache_write_tokens * self.cache_write
        ) / 1_000_000

    def dearest_prompt(self, tokens: int) -> Usage:
        """A prompt's tokens at whichever of input and cache write costs more."""
        if self.cache_write >= self.input:
            return Usage(cache_write_tokens=tokens)
        return Usage(input_tokens=tokens)

    def per_million(self) -> dict[str, float]:
        """Keyed as the ledger keys its tokens."""
        return {
            "input_tokens": self.input,
            "output_tokens": self.output,
            "cache_read_tokens": self.cache_read,
            "cache_write_tokens": self.cache_write,
        }


# platform.claude.com/docs/en/about-claude/pricing, read 4 Oct 2026.
ANTHROPIC_PRICES = {
    "claude-sonnet-5-5": Prices(
        input=2.00, output=10.00, cache_read=0.20, cache_write=2.50
    ),
    "claude-opus-5-5": Prices(
        input=4.00, output=20.00, cache_read=0.20, cache_write=5.00
    ),
    "claude-haiku-4-5": Prices(
        input=1.00, output=5.00, cache_read=0.10, cache_write=1.25
    ),
}


def anthropic_prices(model: str) -> Prices:
    """The table's row; a model it lacks stops the run rather than going uncharged."""
    try:
        return ANTHROPIC_PRICES[model]
    except KeyError:
        raise ValueError(
            f"no Anthropic prices for {model}; add them to ANTHROPIC_PRICES "
            f"(priced: {', '.join(ANTHROPIC_PRICES)})"
        ) from None


def openrouter_prices(model: str, listing_url: str = OPENROUTER_MODELS) -> Prices:
    """OpenRouter's listed rates, which are per token; an unlisted cache rate counts as input."""
    listing = httpx.get(listing_url, timeout=30.0)
    listing.raise_for_status()
    for entry in listing.json()["data"]:
        if entry["id"] == model:
            pricing = entry["pricing"]
            input_ = _per_million(pricing["prompt"], 0.0)
            return Prices(
                input=input_,
                output=_per_million(pricing["completion"], 0.0),
                cache_read=_per_million(pricing.get("input_cache_read"), input_),
                cache_write=_per_million(pricing.get("input_cache_write"), input_),
            )
    raise ValueError(f"OpenRouter does not list {model}")


def _per_million(per_token: str | None, otherwise: float) -> float:
    # Decimal, so "0.0000001" a token is 0.1, not 0.09999999999999999.
    return float(Decimal(per_token) * 1_000_000) if per_token else otherwise
