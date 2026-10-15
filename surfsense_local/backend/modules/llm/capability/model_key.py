"""One key per model across providers, so a row measured on one holds on another."""

import re

__all__ = ["model_key"]

# An alias moves to a new model without its id changing, so it is never the model measured.
_ALIAS = re.compile(r"(^~)|((^|[-:/_.@])latest$)")
# OpenRouter's routing shortcuts pick hosts, not another model.
_ROUTING = re.compile(r":(free|nitro|floor)$")
_DOT_BETWEEN_DIGITS = re.compile(r"(?<=\d)\.(?=\d)")
# An eight-digit snapshot date, as Anthropic and OpenAI date their ids.
_SNAPSHOT = re.compile(r"-20\d{6}$")


def model_key(model_id: str) -> str | None:
    """The canonical key for a provider's model id; None for an alias or no id."""
    raw = model_id.strip().lower()
    if not raw or _ALIAS.search(raw):
        return None
    name = raw.rsplit("/", 1)[-1].split("@", 1)[0]
    name = _ROUTING.sub("", name)
    name = _DOT_BETWEEN_DIGITS.sub("-", name)
    return _SNAPSHOT.sub("", name) or None
