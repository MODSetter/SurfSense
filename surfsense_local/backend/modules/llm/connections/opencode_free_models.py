"""OpenCode's Console refuses its free models outside OpenCode with a 403.

https://opencode.ai/v2/docs/console/harnesses
"""

from urllib.parse import urlsplit

OPENCODE_CONSOLE_PROVIDERS = frozenset({"opencode", "opencode-go"})
FREE_MODEL_REASON = "OpenCode allows its free models only inside OpenCode"

_CONSOLE_HOST = "opencode.ai"
_REFUSED = 403


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
    if provider not in OPENCODE_CONSOLE_PROVIDERS or listed_free is None:
        return from_manifest
    return FREE_MODEL_REASON if listed_free else None


def is_free_model_refusal(url: str, status_code: int) -> bool:
    """A 403 the Console may mean for a typed or already selected free model."""
    return status_code == _REFUSED and urlsplit(url).hostname == _CONSOLE_HOST


def explained_refusal(url: str, status_code: int, message: str) -> str:
    """The endpoint's words, plus the reason where it could be this rule."""
    if not is_free_model_refusal(url, status_code):
        return message
    return f"{message.rstrip('.')}. {FREE_MODEL_REASON}"
