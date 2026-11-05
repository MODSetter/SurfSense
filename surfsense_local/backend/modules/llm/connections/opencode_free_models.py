"""Where OpenCode's free models work, which is narrower on Zen than on Go.

The docs promise a 403 outside OpenCode (https://opencode.ai/v2/docs/console/harnesses).
Live on 5 Nov 2026, a Go key got `beam-free`'s reply and a Zen key got a 429 from all
five free models tried, with the same account.
"""

ZEN_PROVIDER = "opencode"
OPENCODE_CONSOLE_PROVIDERS = frozenset({ZEN_PROVIDER, "opencode-go"})
FREE_MODEL_REASON = (
    "OpenCode's free models work only inside OpenCode or with OpenCode Go"
)


def listed_as_free(entry: dict[str, object]) -> bool | None:
    """What a live listing says, or None when unreadable: its `cost` is undocumented."""
    cost = entry.get("cost")
    text = cost.get("text") if isinstance(cost, dict) else None
    if not isinstance(text, dict):
        return None
    input_price = _price(text.get("input"))
    output_price = _price(text.get("output"))
    if input_price is None or output_price is None:
        return None
    return input_price == 0 and output_price == 0


def _price(side: object) -> float | None:
    price = side.get("price") if isinstance(side, dict) else None
    if isinstance(price, bool) or not isinstance(price, int | float):
        return None
    return price


def unusable_reason(
    provider: str | None, listed_free: bool | None, from_manifest: str | None
) -> str | None:
    """A live price is newer than the manifest, which still decides without one."""
    if provider != ZEN_PROVIDER or listed_free is None:
        return from_manifest
    return FREE_MODEL_REASON if listed_free else None
