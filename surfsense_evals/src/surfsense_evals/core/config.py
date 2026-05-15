"""Environment + filesystem configuration for the harness.

Two responsibilities:

1. Load env vars (with sensible defaults) into a single immutable ``Config``
   so that every other module reads it from one place.
2. Read / write ``data/state.json``. State is keyed by suite name so multiple
   suites can be set up in parallel and torn down independently.

The pinned ``search_space_id`` lives in ``state.json`` (not env) so re-runs
are idempotent without forcing the operator to remember an integer.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Resolve once at import time. ``find_dotenv`` walks up; an explicit ``.env``
# at the package root or in CWD wins. Silent-no-op if neither exists.
load_dotenv()


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
"""Resolves to ``surfsense_evals/`` (the package root, not ``src/``)."""


def _project_root() -> Path:
    """Return the ``surfsense_evals/`` project root.

    Computed from this file's path: ``src/surfsense_evals/core/config.py`` →
    walk up four levels. Kept as a function so tests can monkeypatch.
    """

    return _PROJECT_ROOT


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration."""

    surfsense_api_base: str
    openrouter_api_key: str | None
    openrouter_base_url: str

    # Credentials — exactly ONE mode must be supplied.
    surfsense_jwt: str | None
    surfsense_refresh_token: str | None
    surfsense_user_email: str | None
    surfsense_user_password: str | None

    # Filesystem paths.
    data_dir: Path
    reports_dir: Path

    @property
    def state_path(self) -> Path:
        return self.data_dir / "state.json"

    def has_jwt_mode(self) -> bool:
        return bool(self.surfsense_jwt)

    def has_local_mode(self) -> bool:
        return bool(self.surfsense_user_email and self.surfsense_user_password)

    def credential_mode(self) -> str:
        """Return ``"jwt"``, ``"local"``, or ``"none"`` (no credentials supplied)."""

        if self.has_jwt_mode():
            return "jwt"
        if self.has_local_mode():
            return "local"
        return "none"

    def suite_data_dir(self, suite: str) -> Path:
        return self.data_dir / suite

    def suite_reports_dir(self, suite: str) -> Path:
        return self.reports_dir / suite

    def suite_runs_dir(self, suite: str) -> Path:
        return self.suite_data_dir(suite) / "runs"

    def suite_maps_dir(self, suite: str) -> Path:
        return self.suite_data_dir(suite) / "maps"


def load_config() -> Config:
    """Read the current process env into a ``Config``.

    No validation is performed here; callers (e.g. ``auth.acquire_token``,
    ``cli`` subcommands) decide which fields they require. This keeps
    ``models list`` and ``suites list`` runnable without OpenRouter creds.
    """

    project_root = _project_root()
    data_dir = Path(os.environ.get("EVAL_DATA_DIR") or (project_root / "data")).resolve()
    reports_dir = Path(os.environ.get("EVAL_REPORTS_DIR") or (project_root / "reports")).resolve()
    return Config(
        surfsense_api_base=os.environ.get("SURFSENSE_API_BASE", "http://localhost:8000").rstrip("/"),
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY") or None,
        openrouter_base_url=os.environ.get(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/"),
        surfsense_jwt=os.environ.get("SURFSENSE_JWT") or None,
        surfsense_refresh_token=os.environ.get("SURFSENSE_REFRESH_TOKEN") or None,
        surfsense_user_email=os.environ.get("SURFSENSE_USER_EMAIL") or None,
        surfsense_user_password=os.environ.get("SURFSENSE_USER_PASSWORD") or None,
        data_dir=data_dir,
        reports_dir=reports_dir,
    )


# ---------------------------------------------------------------------------
# state.json — per-suite slots
# ---------------------------------------------------------------------------


# Scenario names — chosen at ``setup`` time, persisted in ``state.json``.
#
# * ``head-to-head`` (default, current behaviour): both arms answer with the
#   SAME slug pinned via ``--provider-model``. Vision LLM at ingest is
#   optional but recommended for image-bearing benchmarks.
# * ``symmetric-cheap``: both arms answer with the SAME (cheap, text-only)
#   slug; SurfSense pre-extracted images at ingest with a vision LLM.
#   Measures whether vision-RAG ingestion lets a cheap downstream model
#   match a vision one. Native arm structurally loses on image questions —
#   that's the point, and the report labels it accordingly.
# * ``cost-arbitrage``: native arm answers with an EXPENSIVE vision slug
#   (``--native-arm-model``), SurfSense answers with a CHEAP text-only slug
#   (``--provider-model``) over chunks the vision LLM already extracted at
#   ingest. Measures how close SurfSense gets to native at a fraction of
#   the per-query cost. The most compelling "shines" framing.
SCENARIOS: tuple[str, ...] = ("head-to-head", "symmetric-cheap", "cost-arbitrage")
DEFAULT_SCENARIO: str = "head-to-head"


@dataclass
class SuiteState:
    """Per-suite persisted state.

    ``provider_model`` is the slug pinned to the SearchSpace's
    ``agent_llm`` — what answers SurfSense queries (and what the native
    arm uses too, unless ``native_arm_model`` is set for cost-arbitrage).

    ``vision_provider_model`` is the slug of the OpenRouter vision LLM
    config attached to the SearchSpace's ``vision_llm_config_id`` — what
    SurfSense uses to extract image content at ingest time when
    ``use_vision_llm=True``. ``None`` means no vision config was attached
    at setup (legacy or text-only suite).
    """

    search_space_id: int
    agent_llm_id: int
    provider_model: str
    created_at: str
    ingestion_maps: dict[str, str] = field(default_factory=dict)
    scenario: str = DEFAULT_SCENARIO
    vision_llm_config_id: int | None = None
    vision_provider_model: str | None = None
    native_arm_model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_space_id": self.search_space_id,
            "agent_llm_id": self.agent_llm_id,
            "provider_model": self.provider_model,
            "created_at": self.created_at,
            "ingestion_maps": dict(self.ingestion_maps),
            "scenario": self.scenario,
            "vision_llm_config_id": self.vision_llm_config_id,
            "vision_provider_model": self.vision_provider_model,
            "native_arm_model": self.native_arm_model,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SuiteState:
        # ``scenario`` / vision / native fields default for back-compat with
        # ``state.json`` written before scenarios shipped.
        scenario = str(payload.get("scenario") or DEFAULT_SCENARIO)
        if scenario not in SCENARIOS:
            scenario = DEFAULT_SCENARIO
        raw_vision_id = payload.get("vision_llm_config_id")
        return cls(
            search_space_id=int(payload["search_space_id"]),
            agent_llm_id=int(payload["agent_llm_id"]),
            provider_model=str(payload["provider_model"]),
            created_at=str(payload.get("created_at") or ""),
            ingestion_maps=dict(payload.get("ingestion_maps") or {}),
            scenario=scenario,
            vision_llm_config_id=int(raw_vision_id) if raw_vision_id is not None else None,
            vision_provider_model=(
                str(payload["vision_provider_model"])
                if payload.get("vision_provider_model")
                else None
            ),
            native_arm_model=(
                str(payload["native_arm_model"])
                if payload.get("native_arm_model")
                else None
            ),
        )

    @property
    def effective_native_arm_model(self) -> str:
        """Slug the native arm should use; falls back to ``provider_model``."""

        return self.native_arm_model or self.provider_model


def _load_state(config: Config) -> dict[str, Any]:
    if not config.state_path.exists():
        return {"suites": {}}
    try:
        with config.state_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Failed to read state file {config.state_path}: {exc!s}. "
            "Delete it if you want to start fresh."
        ) from exc
    if not isinstance(data, dict) or "suites" not in data:
        return {"suites": {}}
    return data


def _write_state(config: Config, payload: Mapping[str, Any]) -> None:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    tmp = config.state_path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(dict(payload), fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(config.state_path)


def get_suite_state(config: Config, suite: str) -> SuiteState | None:
    """Return ``SuiteState`` for ``suite`` or ``None`` if not set up."""

    state = _load_state(config)
    raw = (state.get("suites") or {}).get(suite)
    if not raw:
        return None
    return SuiteState.from_dict(raw)


def set_suite_state(config: Config, suite: str, suite_state: SuiteState) -> None:
    """Persist ``suite_state`` under the suite slot. Other suites are untouched."""

    state = _load_state(config)
    suites = dict(state.get("suites") or {})
    suites[suite] = suite_state.to_dict()
    state["suites"] = suites
    _write_state(config, state)


def clear_suite_state(config: Config, suite: str) -> bool:
    """Remove the slot for ``suite``. Returns ``True`` if removal happened."""

    state = _load_state(config)
    suites = dict(state.get("suites") or {})
    if suite not in suites:
        return False
    del suites[suite]
    state["suites"] = suites
    _write_state(config, state)
    return True


def utc_iso_timestamp() -> str:
    """Filesystem-safe UTC ISO timestamp, e.g. ``2026-05-11T20-30-00Z``."""

    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
