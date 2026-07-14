"""Suite + Benchmark protocols and the global registry.

The extensibility seam: ``core.cli`` walks ``surfsense_evals.suites`` on
import, which auto-imports every benchmark subpackage, which calls
``register(<benchmark>)`` at module bottom. The CLI then iterates the
populated registry to build subcommand groups dynamically.

Adding a new domain = drop a folder under ``suites/<domain>/<bench>/``
that ends in ``register(MyBenchmark())``. No edits anywhere in
``core/`` are required.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx

from .clients import DocumentsClient, NewChatClient, SearchSpaceClient
from .config import Config, SuiteState

# ---------------------------------------------------------------------------
# Run context — what every benchmark.ingest/run receives
# ---------------------------------------------------------------------------


@dataclass
class RunContext:
    """Per-invocation environment threaded into ``ingest`` and ``run``.

    A benchmark uses this to read pinned suite state, build new HTTP
    clients on the shared ``http`` session, find the right data /
    reports paths, and discover the active OpenRouter model + key.

    ``http`` is the authenticated SurfSense client (auth event hook
    attached). It is **not** an OpenRouter client — providers create
    their own short-lived clients because OpenRouter doesn't share the
    SurfSense bearer.
    """

    suite: str
    benchmark: str
    config: Config
    suite_state: SuiteState
    http: httpx.AsyncClient

    @property
    def search_space_id(self) -> int:
        return self.suite_state.search_space_id

    @property
    def chat_model_id(self) -> int:
        return self.suite_state.chat_model_id

    @property
    def provider_model(self) -> str:
        """Slug used by the SurfSense agent (and the native arm by default).

        For ``cost-arbitrage`` scenarios this is the *cheap, text-only*
        slug — SurfSense answers from the chunks the vision LLM already
        extracted at ingest. The native arm should use
        ``native_arm_model`` instead in that scenario.
        """

        return self.suite_state.provider_model

    @property
    def native_arm_model(self) -> str:
        """Slug the native_pdf arm should use.

        Defaults to ``provider_model`` (head-to-head / symmetric-cheap);
        for ``cost-arbitrage`` it returns the explicit
        ``--native-arm-model`` so the native arm can fairly answer
        image-bearing questions.
        """

        return self.suite_state.effective_native_arm_model

    @property
    def vision_provider_model(self) -> str | None:
        """Slug of the OpenRouter vision LLM SurfSense used at ingest.

        ``None`` if no vision config was attached at setup (legacy or
        text-only suite). Used by runners purely to record what was
        actually used in ``RunArtifact.extra`` and to label reports.
        """

        return self.suite_state.vision_provider_model

    @property
    def scenario(self) -> str:
        """Scenario name pinned at setup time (see ``config.SCENARIOS``)."""

        return self.suite_state.scenario

    def search_space_client(self) -> SearchSpaceClient:
        return SearchSpaceClient(self.http, self.config.surfsense_api_base)

    def documents_client(self) -> DocumentsClient:
        return DocumentsClient(self.http, self.config.surfsense_api_base)

    def new_chat_client(self) -> NewChatClient:
        return NewChatClient(self.http, self.config.surfsense_api_base)

    def maps_dir(self) -> Path:
        path = self.config.suite_maps_dir(self.suite)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def runs_dir(self, *, run_timestamp: str) -> Path:
        path = self.config.suite_runs_dir(self.suite) / run_timestamp / self.benchmark
        path.mkdir(parents=True, exist_ok=True)
        return path

    def benchmark_data_dir(self) -> Path:
        path = self.config.suite_data_dir(self.suite) / self.benchmark
        path.mkdir(parents=True, exist_ok=True)
        return path


# ---------------------------------------------------------------------------
# Run artifact + report section
# ---------------------------------------------------------------------------


@dataclass
class RunArtifact:
    """Everything a runner persists for the report writer to consume.

    ``raw_path`` points at the JSONL of per-question ``ArmResult``
    rows. ``metrics`` is a free-form dict the benchmark fills in (e.g.
    ``{"native": {...}, "surfsense": {...}, "delta": {...}}``).
    """

    suite: str
    benchmark: str
    run_timestamp: str
    raw_path: Path
    metrics: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportSection:
    """One benchmark's slice of the final summary."""

    title: str
    headline: bool
    body_md: str
    body_json: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Benchmark protocol + registry
# ---------------------------------------------------------------------------


@runtime_checkable
class Benchmark(Protocol):
    """The contract every benchmark module ends with ``register(<x>)``."""

    suite: str
    name: str
    headline: bool
    description: str

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:  # pragma: no cover - protocol
        ...

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:  # pragma: no cover - protocol
        ...

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:  # pragma: no cover - protocol
        """Add benchmark-specific flags to ``run <suite> <benchmark>``."""

    def report_section(
        self, artifacts: list[RunArtifact]
    ) -> ReportSection:  # pragma: no cover - protocol
        ...


# ---------------------------------------------------------------------------
# Registry storage
# ---------------------------------------------------------------------------


_REGISTRY: dict[tuple[str, str], Benchmark] = {}


def register(benchmark: Benchmark) -> None:
    """Add ``benchmark`` to the registry. Last-wins on duplicate keys.

    Duplicate registrations log a warning rather than raising so a
    benchmark module imported twice (once via auto-discovery, once via
    a test directly importing it) doesn't blow up the CLI.
    """

    key = (benchmark.suite, benchmark.name)
    if key in _REGISTRY:
        import logging

        logging.getLogger(__name__).warning(
            "Benchmark %s/%s re-registered (overwriting prior)", *key
        )
    _REGISTRY[key] = benchmark


def unregister(suite: str, name: str) -> None:
    """Test helper: drop a single benchmark from the registry."""

    _REGISTRY.pop((suite, name), None)


def reset() -> None:
    """Test helper: wipe the registry (use with monkeypatched discovery)."""

    _REGISTRY.clear()


def get(suite: str, name: str) -> Benchmark:
    try:
        return _REGISTRY[(suite, name)]
    except KeyError as exc:
        available = ", ".join(f"{s}/{n}" for s, n in sorted(_REGISTRY)) or "<none>"
        raise KeyError(f"Unknown benchmark '{suite}/{name}'. Registered: {available}") from exc


def list_suites() -> list[str]:
    return sorted({s for s, _ in _REGISTRY})


def list_benchmarks(suite: str | None = None) -> list[Benchmark]:
    if suite is None:
        return [_REGISTRY[k] for k in sorted(_REGISTRY)]
    return [_REGISTRY[k] for k in sorted(_REGISTRY) if k[0] == suite]


def snapshot() -> Mapping[tuple[str, str], Benchmark]:
    """Read-only view for diagnostics (e.g. ``benchmarks list`` rendering)."""

    return dict(_REGISTRY)


__all__ = [
    "Arm",
    "Benchmark",
    "ReportSection",
    "RunArtifact",
    "RunContext",
    "get",
    "list_benchmarks",
    "list_suites",
    "register",
    "reset",
    "snapshot",
    "unregister",
]


# Re-export Arm from arms.base so suites can `from core.registry import Arm`.
from .arms.base import Arm  # noqa: E402, F401  (deliberate re-export at bottom)
