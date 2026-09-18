"""Regenerate the vendored model capability catalogue from models.dev.

`uv run scripts/fetch_model_capabilities.py` rewrites
`modules/llm/connections/model-capabilities.json`, which is committed and
reviewed like source. Nothing fetches models.dev at runtime.

OpenAI-compatible endpoints answer `/models` with bare ids, so the app has no
way to tell a chat model from an embedding model at request time. This script
does that classification once, offline, where a human reads the diff before it
ships.

Capability is derived from the shape of `modalities`, never from the name:
image output means an image model, and a model that does not take text in and
give text out cannot hold a chat. That is exact for image, speech, transcription
and video models.

It cannot separate a chat model from an embedding or classifier model, because
models.dev has no modality for a vector and both end up text-to-text. We accept
that rather than maintain overrides; see CURATED below for what it costs and why.
An id models.dev does not carry is reported "unknown", never guessed.
"""

import collections
import json
import sys
from pathlib import Path

import httpx

SOURCE = "https://models.dev/api.json"
TARGET = (
    Path(__file__).resolve().parents[1]
    / "modules"
    / "llm"
    / "connections"
    / "model-capabilities.json"
)
SCHEMA_VERSION = 1

# Every provider models.dev carries is included, because a connection can point
# at any OpenAI-compatible endpoint: a hosted API, a gateway, or LM Studio, vLLM
# or Ollama on another machine. Narrowing the list would only decide whose models
# get a label and whose do not.
#
# OpenRouter is the single exception, and a structural one: it publishes
# output_modalities on the wire, so its models resolve as "declared" before the
# table is ever consulted. Rows for it would be unreachable by construction.
EXCLUDED_PROVIDERS = ("openrouter",)

CHAT = ["completion"]
IMAGE = ["image_generation"]
NEITHER: list[str] = []

# Deliberately empty, and meant to stay that way.
#
# models.dev is taken verbatim. Hand-written rows would be more accurate for a
# while and then quietly rot, and a stale override is worse than an upstream
# value because nobody re-reads it. Corrections belong upstream, where every
# consumer gets them and we carry nothing.
#
# What that costs is known and bounded: models.dev has no vocabulary for
# "embedding" (its modalities are text/image/audio/video/pdf only), so an
# embedding model reads as text-to-text and is labelled chat. Across every
# first-party provider that is 23 models, 7 of them on an OpenAI key, led by
# text-embedding-3-small. Picking one for chat fails on the first message with
# the endpoint's own explanation rather than being refused up front.
#
# Anything models.dev does not carry at all is reported "unknown", which is the
# honest answer and still reachable through the test dialog. That is where
# babbage-002 and computer-use-preview land, and why they no longer claim to be
# chat models.
#
# If a row is ever added here it wins over the derived value, so add one only
# when the wrong label is blocking real use, and delete it once upstream is fixed.
CURATED: dict[str, list[str]] = {}


def derive(model: dict) -> list[str] | None:
    """Read capabilities off the modality shape, or None when it says nothing.

    The two roles are tested independently, because a model can fill both: a
    model that returns text and images holds a conversation and draws. Testing
    for images first and returning early would silently drop chat from every
    one of them.
    """
    modalities = model.get("modalities")
    if not isinstance(modalities, dict):
        return None
    inputs = set(modalities.get("input") or ())
    outputs = set(modalities.get("output") or ())
    if not inputs or not outputs:
        return None
    capabilities = []
    # Chat needs text both ways: audio in means transcription, audio out speech.
    if "text" in inputs and "text" in outputs:
        capabilities.append("completion")
    if "image" in outputs:
        capabilities.append("image_generation")
    return capabilities


def providers(catalogue: dict) -> list[str]:
    return sorted(p for p in catalogue if p not in EXCLUDED_PROVIDERS)


def collect(catalogue: dict) -> tuple[dict[str, list[str]], list[str], list[str]]:
    """Fold every provider's rows into one id -> capabilities table.

    Returns the table, the ids two providers described differently, and the
    vendor-scoped ids dropped in favour of the bare id they fall back to.
    """
    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for provider in providers(catalogue):
        section = catalogue.get(provider)
        if not isinstance(section, dict):
            continue
        for name, model in section.get("models", {}).items():
            capabilities = derive(model)
            if capabilities is not None:
                votes[name][tuple(capabilities)] += 1

    # Resellers describe other people's models, and a single careless one is
    # common: eleven providers call gpt-5 a chat model and one adds image
    # output. Taking the union would let that one win, so the most-described
    # shape wins instead. A genuine dual-capability model keeps both, because
    # the providers that actually serve it agree.
    derived: dict[str, list[str]] = {}
    conflicts: list[str] = []
    for name, counted in votes.items():
        ranked = counted.most_common()
        if len(ranked) > 1:
            conflicts.append(name)
        top = ranked[0][1]
        winners = [shape for shape, count in ranked if count == top]
        if len(winners) == 1:
            derived[name] = list(winners[0])
            continue
        # A tie says nothing either way, so keep every role any of the tied
        # descriptions claims rather than silently dropping one.
        union = set().union(*(set(shape) for shape in winners))
        derived[name] = [c for c in CHAT + IMAGE if c in union]

    # A gateway re-lists other people's models under its own prefix, and
    # sometimes describes them worse than the vendor does: Poe calls
    # openai/gpt-5.4 an image model. Lookup already falls back from a prefixed
    # id to its last segment, so dropping these rows lets the vendor's own answer
    # stand instead of being shadowed by an exact match on a reseller's row.
    # Curated ids count as answers too, or a gateway's copy of a model we ruled
    # on would outlive the ruling: openai/gpt-realtime-2 must not survive the
    # curated gpt-realtime-2.
    answered = set(derived) | set(CURATED)
    shadowed = sorted(
        name for name in derived if "/" in name and name.rsplit("/", 1)[-1] in answered
    )
    for name in shadowed:
        del derived[name]
    return derived, conflicts, shadowed


def main() -> int:
    print(f"get  {SOURCE}")
    try:
        reply = httpx.get(SOURCE, timeout=120.0, follow_redirects=True)
        reply.raise_for_status()
        catalogue = reply.json()
    except (httpx.HTTPError, ValueError) as error:
        print(f"error: could not read models.dev: {error}", file=sys.stderr)
        return 1

    derived, conflicts, shadowed = collect(catalogue)
    rows = {
        name: {"capabilities": capabilities, "origin": "models.dev"}
        for name, capabilities in derived.items()
    }
    for name, capabilities in CURATED.items():
        rows[name] = {"capabilities": capabilities, "origin": "curated"}

    previous: dict[str, dict] = {}
    if TARGET.exists():
        previous = json.loads(TARGET.read_text()).get("models", {})

    document = {
        "_readme": [
            "GENERATED FILE - do not edit by hand.",
            f"Regenerate with: uv run scripts/{Path(__file__).name}",
            f"Rows marked origin=models.dev are derived from {SOURCE},",
            "by reading modalities.input/output: image out means an image model,",
            "and text in plus text out means a chat model.",
            "models.dev is taken verbatim; we keep no hand-written overrides, so",
            "corrections go upstream to models.dev rather than into this file.",
            "Known limit: models.dev has no modality for a vector, so embedding",
            "models read as text-to-text and are labelled chat. Selecting one for",
            "chat fails on the first message with the endpoint's own explanation.",
            "Every models.dev provider is included except OpenRouter, which",
            "publishes capabilities on the wire and is answered before this file.",
            "A model with no row here is reported as unknown, never guessed.",
        ],
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "excluded_providers": list(EXCLUDED_PROVIDERS),
        "models": dict(sorted(rows.items(), key=lambda row: row[0].casefold())),
    }
    TARGET.write_text(json.dumps(document, indent=2) + "\n")

    added = sorted(set(rows) - set(previous))
    removed = sorted(set(previous) - set(rows))
    changed = sorted(
        name
        for name in set(rows) & set(previous)
        if rows[name]["capabilities"] != previous[name].get("capabilities")
    )
    print(f"wrote {TARGET}")
    print(
        f"  {len(rows)} models ({len(CURATED)} curated), {TARGET.stat().st_size} bytes"
    )
    print(f"  added {len(added)}, changed {len(changed)}, removed {len(removed)}")
    for label, names in (("added", added), ("changed", changed), ("removed", removed)):
        for name in names[:20]:
            print(f"    {label}: {name}")
        if len(names) > 20:
            print(f"    {label}: ... and {len(names) - 20} more")
    print(f"  dropped {len(shadowed)} vendor-scoped id(s) answered by their bare id")
    if conflicts:
        print(
            f"  review: {len(set(conflicts))} id(s) declared differently by providers"
        )
        for name in sorted(set(conflicts))[:40]:
            print(f"    conflict: {name}")
        if len(set(conflicts)) > 40:
            print(f"    conflict: ... and {len(set(conflicts)) - 40} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
