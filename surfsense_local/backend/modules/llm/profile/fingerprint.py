import re

from modules.llm.profile.types import Fingerprint, Line

# A parameter count in a model name. The lookbehind keeps a version out of the
# count (`llama-3.3-70b` is not 3B) and the lookahead keeps a precision out
# (`bf16`, `8bit`, `q4_0` state a weight width, not a size).
_SIZE_B = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", re.IGNORECASE)

# The word a vendor uses in place of a count, in either direction. Delimited,
# because `minimax` ends in one line word and `gemini` in another, and reading
# either as a line demotes a flagship.
_SMALL_LINE = re.compile(
    r"(^|[-/_.])(mini|small|xs|edge|lite|flash|air|nano|tiny)([-/_.0-9]|$)",
    re.IGNORECASE,
)
_FLAGSHIP_LINE = re.compile(
    r"(^|[-/_.])(pro|max|large|plus|ultra|opus|xl)([-/_.0-9]|$)", re.IGNORECASE
)

# Bytes one weight occupies on disk at each quantization, so a blob size divided
# by it is a parameter count.


def from_llamacpp(name: str, props: dict) -> Fingerprint:
    """What the local runtime knows about a loaded model, from `GET /props`.

    The previous runtime divided a blob of quantized weights by a bytes-per-weight
    guess, which read `gemma3:4b` as 5.5B because embedding tables inflate it.
    llama.cpp states the count, so the guess is gone. Where it does not, the
    filename usually carries the size and that still beats measuring.
    """
    stated = (props.get("model_info") or {}).get("general.parameter_count")
    return Fingerprint(
        provider="llamacpp",
        name=name,
        params_b=(
            round(stated / 1e9, 1) if stated else _largest_size_b(name)
        ),
    )


def from_remote(name: str, rows: list[dict]) -> Fingerprint:
    """What the /v1/models listing reveals about one hosted model."""
    row = _row(name, rows)
    # The variant suffix picks a routing tier (`:free`, `:nitro`), not a model.
    described = (row.get("id") or name).partition(":")[0]
    repo = row.get("hugging_face_id")
    if not repo:
        return Fingerprint(
            provider="openai_compatible",
            name=name,
            vendor=row.get("owned_by") or described.rpartition("/")[0],
        )
    return Fingerprint(
        provider="openai_compatible",
        name=name,
        params_b=_largest_size_b(described) or _largest_size_b(repo),
        # Published weights with no size word are that vendor's full-size model:
        # nobody pays to host a small one.
        line=_line(described) or Line.FLAGSHIP,
    )


def _row(name: str, rows: list[dict]) -> dict:
    """The row describing a model: its own, else its base id's, else its alias's."""
    by_id = {row.get("id"): row for row in rows}
    row = by_id.get(name) or by_id.get(name.partition(":")[0]) or {}
    alias = row.get("alias_target") or {}
    return by_id.get(alias.get("slug") if isinstance(alias, dict) else None) or row


def from_name(provider: str, name: str) -> Fingerprint:
    """What a model's name alone reveals, for endpoints that expose no metadata."""
    stated = _largest_size_b(name)
    if stated is not None:
        return Fingerprint(provider=provider, name=name, params_b=stated)
    return Fingerprint(provider=provider, name=name, line=_line(name))


def _largest_size_b(text: str) -> float | None:
    """The largest count stated, so a mixture of experts reads total, not active."""
    sizes = [float(size) for size in _SIZE_B.findall(text)]
    return max(sizes) if sizes else None


def _line(name: str) -> Line | None:
    """The line a name states outright. None means it states none."""
    # The publisher prefix names a company, never a line: `minimax/minimax-m3`.
    model = name.rsplit("/", 1)[-1]
    if _SMALL_LINE.search(model):
        return Line.SMALL
    if _FLAGSHIP_LINE.search(model):
        return Line.FLAGSHIP
    return None
