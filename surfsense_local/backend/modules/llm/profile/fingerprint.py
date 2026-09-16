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
_BYTES_PER_WEIGHT = (("q4", 0.6), ("q5", 0.7), ("q6", 0.82), ("q8", 1.06), ("f16", 2.0))


def from_ollama(name: str, tag: dict, show: dict) -> Fingerprint:
    """What Ollama knows about an installed model, from /api/tags and /api/show."""
    exact = (show.get("model_info") or {}).get("general.parameter_count")
    stated = (tag.get("details") or {}).get("parameter_size") or ""
    return Fingerprint(
        provider="ollama",
        name=name,
        params_b=(
            round(exact / 1e9, 1)
            if exact
            # The tag itself usually states the size, and beats measuring the blob.
            else _largest_size_b(stated) or _largest_size_b(name) or _estimated_b(tag)
        ),
    )


def _estimated_b(tag: dict) -> float | None:
    """The parameter count a blob of quantized weights implies.

    ponytail: it measures weights only, so large embedding tables inflate it
    (gemma3:4b reads 5.5B) and a model within ~20% of a threshold can land in the
    wrong tier. Upgrade path: read the count from the GGUF header.
    """
    size = tag.get("size")
    quantization = ((tag.get("details") or {}).get("quantization_level") or "").lower()
    per_weight = next(
        (
            bytes_
            for prefix, bytes_ in _BYTES_PER_WEIGHT
            if quantization.startswith(prefix)
        ),
        None,
    )
    if not size or per_weight is None:
        return None
    return round(size / per_weight / 1e9, 1)


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
