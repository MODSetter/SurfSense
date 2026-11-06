"""What a word-clauses job brings in its pack: its review points, its prompts, and how much of the
contract and the playbook each call reads.

The runner is the app's; everything here is the job's own content, read from the pack.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from modules.jobs.packs.manifest import PackRefusedError, safe_path
from modules.jobs.settings.declared import (
    JobSetting,
    declared_settings,
    setting_values,
)

_KEY = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

# The words around the model's own in each comment, where the pack gives none.
DEFAULT_TEMPLATES = {
    "note": "SurfSense, $title: $note\nYour playbook ($source): “$quote”",
    "person": "SurfSense could not settle $title: $why",
    "summary": (
        "SurfSense reviewed $points points against your playbook: $changed changed, "
        "$meets meet it, $not_covered not covered by it, $for_person for a person."
    ),
}


@dataclass(frozen=True)
class ReviewPoint:
    key: str
    title: str
    covers: str  # what a position on the point is about, as the model reads it
    queries: tuple[str, ...] = ()  # words a firm's playbook may use for it


@dataclass(frozen=True)
class ClauseConfig:
    points: tuple[ReviewPoint, ...]
    system_prompt: str
    point_prompt: str
    repair_prompt: str
    check_prompt: str = ""  # empty: a change is not checked a second time
    templates: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_TEMPLATES)
    )
    min_quote_chars: int = 15
    passages_per_point: int = 6
    # Shares of the model's window the playbook and the contract may fill in every call: together
    # 60%, so a 32K local window keeps room for the instructions and a thinking model's reply.
    sources_share: float = 0.25
    max_sources_chars: int = 60_000
    contract_share: float = 0.35
    max_contract_chars: int = 160_000
    # Clauses a call is shown when the whole contract does not fit.
    clauses_per_point: int = 16
    settings: tuple[JobSetting, ...] = ()

    def setting_values(self, chosen: Mapping[str, object] | None) -> dict[str, bool]:
        """Every setting the job declares, as the firm chose it or at its default."""
        return setting_values(self.settings, chosen)


def load_config(config_file: Path) -> ClauseConfig:
    folder = config_file.parent
    try:
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        prompts = raw["prompts"]
        config = ClauseConfig(
            points=tuple(_point(item) for item in raw["points"]),
            system_prompt=_prompt(folder, prompts["system"]),
            point_prompt=_prompt(folder, prompts["point"]),
            repair_prompt=_prompt(folder, prompts["repair"]),
            check_prompt=_prompt(folder, prompts["check"])
            if prompts.get("check")
            else "",
            templates={**DEFAULT_TEMPLATES, **_templates(raw.get("templates", {}))},
            min_quote_chars=int(raw.get("min_quote_chars", 15)),
            passages_per_point=int(raw.get("passages_per_point", 6)),
            sources_share=_share(raw.get("sources_share", 0.25)),
            max_sources_chars=int(raw.get("max_sources_chars", 60_000)),
            contract_share=_share(raw.get("contract_share", 0.35)),
            max_contract_chars=int(raw.get("max_contract_chars", 160_000)),
            clauses_per_point=int(raw.get("clauses_per_point", 16)),
            settings=declared_settings(raw.get("settings", ())),
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise PackRefusedError(
            "BAD_JOB_CONFIG", f"The job's config cannot be read: {error}"
        ) from error
    if not config.points:
        raise PackRefusedError("BAD_JOB_CONFIG", "The job has no review points.")
    keys = [p.key for p in config.points]
    if len(set(keys)) != len(keys):
        raise PackRefusedError("BAD_JOB_CONFIG", "Two review points share a key.")
    return config


def _point(item: dict) -> ReviewPoint:
    key, title = str(item["key"]), str(item["title"]).strip()
    if not _KEY.match(key) or not title:
        raise ValueError(f"review point {key!r} needs a key and a title")
    return ReviewPoint(
        key=key,
        title=title,
        covers=str(item.get("covers", "")).strip(),
        queries=tuple(str(q) for q in item.get("queries", ())),
    )


def _templates(raw: dict) -> dict[str, str]:
    unknown = set(raw) - set(DEFAULT_TEMPLATES)
    if unknown:
        raise ValueError(f"no template named {', '.join(sorted(unknown))}")
    return {str(k): str(v) for k, v in raw.items()}


def _share(value: object) -> float:
    share = float(value)  # type: ignore[arg-type]
    if not 0 < share <= 1:
        raise ValueError("a share of the window is above 0 and at most 1")
    return share


def _prompt(folder: Path, relative: str) -> str:
    return (folder / safe_path(relative)).read_text(encoding="utf-8").strip()
