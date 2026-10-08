"""Which OpenRouter models the screening sweep runs, and which flagships it assumes pass without a run.

A model is kept when it calls tools, holds 32k tokens, is a fixed model (no free
or batch tier, no alias, no OpenRouter router) and has prices. One model per
model_key, its cheapest variant. Keys a run measured keep their rows; an assumed
flagship is chosen again.
"""

import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from modules.llm.capability.measured.schema import ASSUMED_SUITE
from modules.llm.capability.model_key import model_key

LISTING_URL = "https://openrouter.ai/api/v1/models"
MIN_CONTEXT = 32_768
# Input at $3/M and up: the dearest flagships, assumed to pass instead of paid for.
ASSUMED_FROM = Decimal(3)
# The maintainer's rule for live runs: never the dearest Claude models.
_NEVER_RUN = re.compile(r"opus|fable", re.IGNORECASE)
_MEASURED = (
    Path(__file__).resolve().parents[3]
    / "modules"
    / "llm"
    / "capability"
    / "measured"
    / "capabilities.json"
)


@dataclass(frozen=True)
class ListedModel:
    id: str
    key: str
    # Dollars per million tokens, as listed.
    prompt: float
    completion: float
    context_length: int
    reads_images: bool

    @property
    def folder(self) -> str:
        return re.sub(r'[<>:"/\\|?*]+', "__", self.id)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "ListedModel":
        return cls(**raw)


@dataclass(frozen=True)
class Selection:
    sweep: list[ListedModel]
    assumed: list[ListedModel]
    # Keys that pass the filters, before the measured ones are left out.
    eligible: int
    measured: list[str]


def select(
    listing: dict[str, Any], measured: set[str], assume: frozenset[str] = frozenset()
) -> Selection:
    """The models to run and the ones assumed, in the listing's order (newest first).

    `assume` names models taken as flagships whatever their price: those that cost
    too much per case to run, by the maintainer's call.
    """
    unknown = sorted(assume - {entry["id"] for entry in listing["data"]})
    if unknown:
        raise ValueError(f"OpenRouter does not list {', '.join(unknown)}")
    cheapest: dict[str, tuple[Decimal, Decimal, ListedModel]] = {}
    for entry in listing["data"]:
        listed = _eligible(entry)
        if listed is None:
            continue
        prompt, completion, model = listed
        kept = cheapest.get(model.key)
        if kept is None or (prompt, completion) < kept[:2]:
            cheapest[model.key] = (prompt, completion, model)
    sweep, assumed, left_out = [], [], []
    for prompt, _, model in cheapest.values():
        if model.key in measured:
            left_out.append(model.key)
        elif prompt >= ASSUMED_FROM or model.id in assume:
            assumed.append(model)
        elif not _NEVER_RUN.search(model.id):
            sweep.append(model)
    return Selection(sweep, assumed, len(cheapest), sorted(left_out))


def pick(listing: dict[str, Any], ids: list[str]) -> list[ListedModel]:
    """Exactly these ids, measured or not, for a pilot or a re-run."""
    by_id = {entry["id"]: entry for entry in listing["data"]}
    picked = []
    for model_id in ids:
        if model_id not in by_id:
            raise ValueError(f"OpenRouter does not list {model_id}")
        if _NEVER_RUN.search(model_id):
            raise ValueError(f"{model_id} is never run by a sweep")
        listed = _eligible(by_id[model_id])
        if listed is None:
            raise ValueError(f"{model_id} does not pass the sweep's filters")
        picked.append(listed[2])
    return picked


def measured_keys(path: Path = _MEASURED) -> set[str]:
    """Every key a shipped row that was run matches: an assumed flagship is
    still chosen, to be screened once its price falls under $3."""
    rows = json.loads(path.read_text(encoding="utf-8"))["models"]
    return {
        key
        for row in rows
        if row["suite"] != ASSUMED_SUITE
        for key in row["match"]["keys"]
    }


def read_listing(path: Path) -> dict[str, Any]:
    """A saved OpenRouter /models listing."""
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_listing(url: str = LISTING_URL) -> dict[str, Any]:
    """OpenRouter's public listing, no key needed."""
    reply = httpx.get(url, timeout=60.0)
    reply.raise_for_status()
    return reply.json()


def _eligible(
    entry: dict[str, Any],
) -> tuple[Decimal, Decimal, ListedModel] | None:
    model_id = entry["id"]
    if "tools" not in (entry.get("supported_parameters") or []):
        return None
    if (entry.get("context_length") or 0) < MIN_CONTEXT:
        return None
    if model_id.endswith((":free", ":batch")) or model_id.startswith(
        ("~", "openrouter/")
    ):
        return None
    pricing = entry.get("pricing") or {}
    try:
        prompt = Decimal(pricing["prompt"]) * 1_000_000
        completion = Decimal(pricing["completion"]) * 1_000_000
    except (KeyError, ArithmeticError, TypeError):
        return None
    if prompt < 0 or completion < 0:
        return None
    key = model_key(model_id)
    if key is None:
        return None
    modalities = (entry.get("architecture") or {}).get("input_modalities") or []
    return (
        prompt,
        completion,
        ListedModel(
            id=model_id,
            key=key,
            prompt=float(prompt),
            completion=float(completion),
            context_length=int(entry["context_length"]),
            reads_images="image" in modalities,
        ),
    )
