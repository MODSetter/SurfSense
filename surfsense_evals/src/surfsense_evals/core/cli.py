"""Argparse CLI for ``python -m surfsense_evals``.

Subcommands:

* ``setup    --suite <name> --provider-model <slug> [--agent-llm-id <int>]``
* ``teardown --suite <name>``
* ``models  list [--provider openrouter] [--grep <s>]``
* ``suites  list``
* ``benchmarks list [--suite <name>]``
* ``ingest <suite> <benchmark> [benchmark flags]``
* ``run    <suite> <benchmark> [benchmark flags]``
* ``report --suite <name> [--benchmark <name>]``

The ``ingest`` / ``run`` subparsers are built dynamically from the
registry — adding a new benchmark only requires registering it; the
CLI surface comes for free. ``add_run_args`` lets each benchmark
publish its own flags.

Design choices worth flagging:

* ``setup`` rejects ``agent_llm_id == 0`` (Auto / LiteLLM router) so
  per-question accuracy is reproducible.
* ``setup`` validates that the picked LLM config has
  ``provider == "OPENROUTER"`` and ``model_name == --provider-model``
  before declaring success — both arms of the head-to-head must hit
  the same OpenRouter slug.
* Lifecycle state is keyed by suite, so ``setup --suite legal`` does
  not touch ``medical``'s SearchSpace, and vice versa.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from typing import Any

import sys

import httpx
from rich.console import Console
from rich.table import Table

# Windows' legacy console (cp1252) crashes when Rich tries to write characters
# outside the active codepage (e.g. '->', em-dashes, box-drawing). Force UTF-8
# on stdout/stderr and disable Rich's legacy_windows render path so the file
# stream is used directly. Modern Windows (>=10, VS Code terminal, Windows
# Terminal, PowerShell, cmd) all interpret ANSI escapes natively.
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

from . import registry
from .auth import CredentialError, acquire_token, client_with_auth
from .clients import SearchSpaceClient
from .clients.search_space import LlmPreferences
from .config import (
    DEFAULT_SCENARIO,
    SCENARIOS,
    Config,
    SuiteState,
    clear_suite_state,
    get_suite_state,
    load_config,
    set_suite_state,
    utc_iso_timestamp,
)
from .vision_llm import VisionConfigError, resolve_vision_llm

logger = logging.getLogger("surfsense_evals")
console = Console(legacy_windows=False)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _discover_suites() -> list[str]:
    """Trigger ``register(...)`` for every benchmark.

    Imported lazily so ``models list`` (which doesn't need any
    benchmark) still runs fast.
    """

    from surfsense_evals.suites import discover_suites

    return discover_suites()


# ---------------------------------------------------------------------------
# Global LLM config fetcher (used by setup + models list)
# ---------------------------------------------------------------------------


@dataclass
class LlmConfigEntry:
    id: int
    name: str
    provider: str
    model_name: str
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> LlmConfigEntry:
        return cls(
            id=int(payload["id"]),
            name=str(payload.get("name", "")),
            provider=str(payload.get("provider", "")).upper(),
            model_name=str(payload.get("model_name", "")),
            raw=payload,
        )


async def _list_global_llm_configs(http: httpx.AsyncClient, base: str) -> list[LlmConfigEntry]:
    response = await http.get(
        f"{base}/api/v1/global-new-llm-configs",
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected /global-new-llm-configs payload: {payload!r}")
    return [LlmConfigEntry.from_payload(item) for item in payload]


def _resolve_openrouter_id(
    candidates: list[LlmConfigEntry],
    provider_model: str,
    *,
    explicit_id: int | None,
) -> int:
    """Resolve the SurfSense LLM id for ``provider_model``.

    Behaviour:

    * If ``explicit_id`` is given: return it directly. The caller is
      then expected to GET-validate that the row's
      ``provider == "OPENROUTER"`` and ``model_name`` matches the slug.
      That branch supports positive BYOK ``NewLLMConfig`` rows whose
      slugs may overlap with global OpenRouter virtuals.
    * Otherwise: filter to ``provider == "OPENROUTER"`` and
      ``model_name == provider_model``. Expect exactly one match —
      raise with a friendly message otherwise.
    """

    if explicit_id is not None:
        return explicit_id

    matches = [
        c for c in candidates if c.provider == "OPENROUTER" and c.model_name == provider_model
    ]
    if not matches:
        sample = ", ".join(
            f"{c.model_name} (id={c.id})" for c in candidates if c.provider == "OPENROUTER"
        )[:600]
        raise RuntimeError(
            f"No OpenRouter config found for slug '{provider_model}'. "
            "Make sure `openrouter_integration.enabled: true` in "
            "global_llm_config.yaml and that the Celery worker has "
            "finished its first refresh (the catalogue is fetched at "
            "Celery startup per `app/celery_app.py`). "
            f"Available OpenRouter slugs (sample): {sample or '<none>'}.\n"
            "Browse with: python -m surfsense_evals models list --grep <substring>"
        )
    if len(matches) > 1:
        listing = "\n".join(f"  id={c.id}  name={c.name!r}" for c in matches)
        raise RuntimeError(
            f"Multiple OpenRouter configs for slug '{provider_model}':\n{listing}\n"
            "Pass --agent-llm-id <id> to disambiguate."
        )
    return matches[0].id


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


async def _cmd_setup(args: argparse.Namespace) -> int:
    suite = args.suite
    provider_model: str = args.provider_model
    explicit_id: int | None = args.agent_llm_id
    scenario: str = args.scenario
    vision_llm_slug: str | None = args.vision_llm
    native_arm_model: str | None = args.native_arm_model
    skip_vision_setup: bool = args.no_vision_llm_setup

    if explicit_id == 0:
        console.print(
            "[red]agent_llm_id == 0 (Auto / LiteLLM router) is not allowed — "
            "results would not be reproducible.[/red]"
        )
        return 2

    if scenario not in SCENARIOS:
        console.print(
            f"[red]Unknown scenario {scenario!r}. Pick one of: "
            f"{', '.join(SCENARIOS)}[/red]"
        )
        return 2

    # Scenario-specific validation. Each branch documents WHY the rule
    # exists so the operator's mental model matches what the runner does.
    if scenario == "cost-arbitrage":
        if not native_arm_model:
            console.print(
                "[red]--scenario cost-arbitrage requires --native-arm-model "
                "<vision-capable slug>.[/red] The native arm needs a vision "
                "model to fairly answer image-bearing questions; SurfSense "
                "answers from already-extracted text via --provider-model."
            )
            return 2
        if native_arm_model == provider_model:
            console.print(
                "[yellow]--native-arm-model equals --provider-model in "
                "cost-arbitrage; that's degenerate (same as head-to-head). "
                "Pick a different slug or switch to --scenario head-to-head.[/yellow]"
            )
    elif scenario in ("head-to-head", "symmetric-cheap"):
        if native_arm_model:
            console.print(
                f"[yellow]--native-arm-model is ignored for --scenario {scenario} "
                f"(both arms answer with --provider-model={provider_model!r}).[/yellow]"
            )
            native_arm_model = None  # don't persist a stale value

    config = load_config()
    try:
        token = await acquire_token(config)
    except CredentialError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2

    async with client_with_auth(config, token) as http:
        candidates = await _list_global_llm_configs(http, config.surfsense_api_base)

        try:
            agent_llm_id = _resolve_openrouter_id(
                candidates, provider_model, explicit_id=explicit_id
            )
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            return 2

        ss_client = SearchSpaceClient(http, config.surfsense_api_base)
        existing = get_suite_state(config, suite)
        if existing is not None:
            try:
                row = await ss_client.get(existing.search_space_id)
                console.print(
                    f"Reusing existing SearchSpace [cyan]{row.name}[/cyan] "
                    f"(id={row.id}) for suite [bold]{suite}[/bold]."
                )
                search_space_id = row.id
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    console.print(
                        f"[yellow]state.json pointed at SearchSpace id={existing.search_space_id} "
                        f"but backend returned 404; creating a fresh one.[/yellow]"
                    )
                    existing = None
                else:
                    raise
        if existing is None:
            ss_name = f"eval-{suite}-{utc_iso_timestamp()}"
            row = await ss_client.create(
                ss_name, description=f"surfsense-evals lifecycle ({suite})"
            )
            console.print(
                f"Created SearchSpace [cyan]{row.name}[/cyan] (id={row.id}) "
                f"for suite [bold]{suite}[/bold]."
            )
            search_space_id = row.id

        # Resolve + attach the vision LLM config (unless explicitly skipped).
        # Asymmetric scenarios make the vision LLM at ingest a hard
        # requirement — without it, SurfSense's chunks have no image
        # content and the entire framing collapses.
        vision_required = scenario in ("symmetric-cheap", "cost-arbitrage")
        vision_config_id: int | None = None
        vision_provider_model: str | None = None
        if not skip_vision_setup and (vision_required or vision_llm_slug is not None):
            try:
                vision_candidates = await ss_client.list_global_vision_llm_configs()
                resolved = resolve_vision_llm(
                    vision_candidates, explicit_slug=vision_llm_slug
                )
            except VisionConfigError as exc:
                console.print(f"[red]{exc}[/red]")
                return 2
            vision_config_id = resolved.config_id
            vision_provider_model = resolved.provider_model
            console.print(
                f"Vision LLM at ingest: [cyan]{vision_provider_model}[/cyan] "
                f"(id={vision_config_id}, selected_via={resolved.selected_via})."
            )

        pref_kwargs: dict[str, Any] = {"agent_llm_id": agent_llm_id}
        if vision_config_id is not None:
            pref_kwargs["vision_llm_config_id"] = vision_config_id

        await ss_client.set_llm_preferences(search_space_id, **pref_kwargs)
        prefs = await ss_client.get_llm_preferences(search_space_id)
        if not _validate_pin(prefs, provider_model):
            agent = prefs.agent_llm or {}
            console.print(
                f"[red]LLM pin validation FAILED.[/red] After PUT, "
                f"agent_llm.provider={agent.get('provider')!r}, "
                f"model_name={agent.get('model_name')!r}; expected "
                f"provider=OPENROUTER, model_name={provider_model!r}."
            )
            return 2
        if vision_config_id is not None and prefs.vision_llm_config_id != vision_config_id:
            console.print(
                f"[red]Vision LLM pin validation FAILED.[/red] After PUT, "
                f"vision_llm_config_id={prefs.vision_llm_config_id!r}; "
                f"expected {vision_config_id!r}."
            )
            return 2

        suite_state = SuiteState(
            search_space_id=search_space_id,
            agent_llm_id=agent_llm_id,
            provider_model=provider_model,
            created_at=utc_iso_timestamp(),
            ingestion_maps=existing.ingestion_maps if existing else {},
            scenario=scenario,
            vision_llm_config_id=vision_config_id,
            vision_provider_model=vision_provider_model,
            native_arm_model=native_arm_model,
        )
        set_suite_state(config, suite, suite_state)

    summary_bits = [
        f"suite={suite!r}",
        f"scenario={scenario!r}",
        f"search_space_id={suite_state.search_space_id}",
        f"agent_llm_id={suite_state.agent_llm_id}",
        f"provider_model={suite_state.provider_model!r}",
    ]
    if suite_state.vision_provider_model:
        summary_bits.append(f"vision_provider_model={suite_state.vision_provider_model!r}")
    if suite_state.native_arm_model:
        summary_bits.append(f"native_arm_model={suite_state.native_arm_model!r}")
    console.print(f"[green]setup OK[/green] {' '.join(summary_bits)}")
    return 0


def _validate_pin(prefs: LlmPreferences, provider_model: str) -> bool:
    agent = prefs.agent_llm or {}
    return (
        str(agent.get("provider", "")).upper() == "OPENROUTER"
        and str(agent.get("model_name", "")) == provider_model
    )


async def _cmd_teardown(args: argparse.Namespace) -> int:
    suite = args.suite
    config = load_config()
    state = get_suite_state(config, suite)
    if state is None:
        console.print(f"[yellow]No state for suite {suite!r}; nothing to tear down.[/yellow]")
        return 0
    try:
        token = await acquire_token(config)
    except CredentialError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2
    async with client_with_auth(config, token) as http:
        ss_client = SearchSpaceClient(http, config.surfsense_api_base)
        try:
            await ss_client.delete(state.search_space_id)
        except httpx.HTTPStatusError as exc:
            console.print(
                f"[yellow]DELETE failed (HTTP {exc.response.status_code}); "
                "clearing state.json anyway.[/yellow]"
            )
    clear_suite_state(config, suite)
    console.print(
        f"[green]teardown OK[/green] suite={suite!r} "
        f"(SearchSpace soft-deleted, state.json slot cleared)."
    )
    return 0


async def _cmd_models_list(args: argparse.Namespace) -> int:
    config = load_config()
    try:
        token = await acquire_token(config)
    except CredentialError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2
    async with client_with_auth(config, token) as http:
        entries = await _list_global_llm_configs(http, config.surfsense_api_base)
    grep = (args.grep or "").lower()
    provider_filter = (args.provider or "").upper()
    rows: list[LlmConfigEntry] = []
    for e in entries:
        if provider_filter and e.provider != provider_filter:
            continue
        if grep and grep not in e.model_name.lower() and grep not in e.name.lower():
            continue
        rows.append(e)
    table = Table(
        title=f"Global LLM configs ({len(rows)} of {len(entries)})",
        show_lines=False,
    )
    table.add_column("id", justify="right", style="cyan")
    table.add_column("provider", style="magenta")
    table.add_column("model_name", style="green")
    table.add_column("name")
    for e in sorted(rows, key=lambda x: (x.provider, x.model_name)):
        table.add_row(str(e.id), e.provider, e.model_name, e.name)
    console.print(table)
    return 0


def _cmd_suites_list(_args: argparse.Namespace) -> int:
    _discover_suites()
    suites = registry.list_suites()
    if not suites:
        console.print(
            "[yellow]No suites registered. Drop a benchmark under "
            "src/surfsense_evals/suites/<domain>/<benchmark>/.[/yellow]"
        )
        return 0
    table = Table(title=f"Registered suites ({len(suites)})")
    table.add_column("suite", style="bold")
    table.add_column("benchmarks", style="green")
    for suite in suites:
        names = [b.name for b in registry.list_benchmarks(suite)]
        table.add_row(suite, ", ".join(names) or "<none>")
    console.print(table)
    return 0


def _cmd_benchmarks_list(args: argparse.Namespace) -> int:
    _discover_suites()
    benchmarks = registry.list_benchmarks(args.suite)
    if not benchmarks:
        console.print("[yellow]No benchmarks registered.[/yellow]")
        return 0
    table = Table(title=f"Benchmarks ({len(benchmarks)})")
    table.add_column("suite", style="bold")
    table.add_column("name", style="cyan")
    table.add_column("headline", justify="center")
    table.add_column("description")
    for b in benchmarks:
        table.add_row(
            b.suite,
            b.name,
            "yes" if b.headline else "no",
            getattr(b, "description", ""),
        )
    console.print(table)
    return 0


async def _cmd_ingest(args: argparse.Namespace) -> int:
    benchmark = registry.get(args.suite, args.benchmark)
    config = load_config()
    state = get_suite_state(config, args.suite)
    if state is None:
        console.print(
            f"[red]No setup for suite {args.suite!r}. Run "
            f"`python -m surfsense_evals setup --suite {args.suite} "
            f"--provider-model <slug>` first.[/red]"
        )
        return 2
    try:
        token = await acquire_token(config)
    except CredentialError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2

    # Forward parsed CLI flags into ingest() so a benchmark can honour
    # its own flags (e.g. MIRAGE's --skip-snippet-filter / --corpus).
    extra_kwargs = {
        k: v
        for k, v in vars(args).items()
        if k not in {"_func", "_async", "command", "subcommand", "suite", "benchmark", "log_level"}
    }
    async with client_with_auth(config, token) as http:
        ctx = registry.RunContext(
            suite=args.suite,
            benchmark=args.benchmark,
            config=config,
            suite_state=state,
            http=http,
        )
        await benchmark.ingest(ctx, **extra_kwargs)
    console.print(f"[green]ingest OK[/green] {args.suite}/{args.benchmark}")
    return 0


async def _cmd_run(args: argparse.Namespace) -> int:
    benchmark = registry.get(args.suite, args.benchmark)
    config = load_config()
    state = get_suite_state(config, args.suite)
    if state is None:
        console.print(
            f"[red]No setup for suite {args.suite!r}. Run "
            f"`python -m surfsense_evals setup --suite {args.suite} "
            f"--provider-model <slug>` first.[/red]"
        )
        return 2
    try:
        token = await acquire_token(config)
    except CredentialError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2

    extra_kwargs = {
        k: v
        for k, v in vars(args).items()
        if k not in {"_func", "_async", "command", "subcommand", "suite", "benchmark", "log_level"}
    }
    async with client_with_auth(config, token) as http:
        ctx = registry.RunContext(
            suite=args.suite,
            benchmark=args.benchmark,
            config=config,
            suite_state=state,
            http=http,
        )
        artifact = await benchmark.run(ctx, **extra_kwargs)

    console.print(
        f"[green]run OK[/green] {args.suite}/{args.benchmark} → "
        f"{artifact.raw_path}"
    )
    return 0


async def _cmd_report(args: argparse.Namespace) -> int:
    from .report import write_report

    benchmark_filter = args.benchmark
    config = load_config()
    state = get_suite_state(config, args.suite)
    if state is None:
        console.print(f"[red]No setup for suite {args.suite!r}.[/red]")
        return 2
    benchmarks = registry.list_benchmarks(args.suite)
    if benchmark_filter:
        benchmarks = [b for b in benchmarks if b.name == benchmark_filter]
        if not benchmarks:
            console.print(
                f"[red]No registered benchmark named {benchmark_filter!r} in suite {args.suite!r}.[/red]"
            )
            return 2

    artifacts = _collect_artifacts(config, args.suite, [b.name for b in benchmarks])
    if not artifacts:
        console.print(
            "[yellow]No run artifacts found under "
            f"{config.suite_runs_dir(args.suite)}. Run a benchmark first.[/yellow]"
        )
        return 1

    grouped: dict[str, list[registry.RunArtifact]] = {}
    for art in artifacts:
        grouped.setdefault(art.benchmark, []).append(art)
    sections: list[registry.ReportSection] = []
    for benchmark in benchmarks:
        if benchmark.name not in grouped:
            continue
        sections.append(benchmark.report_section(grouped[benchmark.name]))

    summary_path = write_report(
        config=config,
        suite=args.suite,
        sections=sections,
        run_timestamp=utc_iso_timestamp(),
    )
    console.print(f"[green]report OK[/green] → {summary_path}")
    return 0


def _collect_artifacts(
    config: Config, suite: str, benchmark_names: list[str]
) -> list[registry.RunArtifact]:
    """Walk ``data/<suite>/runs/*/<benchmark>/`` for the latest artifacts.

    Reads any ``run_artifact.json`` written by a benchmark runner. The
    runner is responsible for writing this manifest alongside its raw
    JSONL so the report writer doesn't have to know benchmark-specific
    metric shapes.
    """

    runs_dir = config.suite_runs_dir(suite)
    if not runs_dir.exists():
        return []
    artifacts: list[registry.RunArtifact] = []
    by_bench: dict[str, registry.RunArtifact] = {}
    for ts_dir in sorted(runs_dir.iterdir()):
        if not ts_dir.is_dir():
            continue
        for bench_name in benchmark_names:
            bench_dir = ts_dir / bench_name
            manifest = bench_dir / "run_artifact.json"
            if not manifest.exists():
                continue
            try:
                with manifest.open("r", encoding="utf-8") as fh:
                    payload = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue
            artifact = registry.RunArtifact(
                suite=suite,
                benchmark=bench_name,
                run_timestamp=ts_dir.name,
                raw_path=bench_dir / payload.get("raw_path", "raw.jsonl"),
                metrics=payload.get("metrics", {}),
                extra=payload.get("extra", {}),
            )
            # Latest run wins per benchmark.
            by_bench[bench_name] = artifact
    artifacts = list(by_bench.values())
    return artifacts


# ---------------------------------------------------------------------------
# Argparse wiring
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="surfsense-evals",
        description="SurfSense evaluation harness — domain-agnostic core + pluggable suites.",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_setup = sub.add_parser("setup", help="Create per-suite SearchSpace + pin LLM.")
    p_setup.add_argument("--suite", required=True)
    p_setup.add_argument(
        "--provider-model",
        required=True,
        help=(
            "OpenRouter slug for the SurfSense answer LLM (and the native arm "
            "too unless --native-arm-model is set), e.g. "
            "'anthropic/claude-sonnet-4.5'."
        ),
    )
    p_setup.add_argument(
        "--agent-llm-id",
        type=int,
        default=None,
        help="Optional override for BYOK NewLLMConfig rows.",
    )
    p_setup.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default=DEFAULT_SCENARIO,
        help=(
            "head-to-head (default): both arms answer with --provider-model; "
            "symmetric-cheap: both arms use the same cheap text-only slug, "
            "SurfSense pre-extracted images at ingest with a vision LLM; "
            "cost-arbitrage: native arm uses --native-arm-model (vision), "
            "SurfSense uses --provider-model (cheap, text-only) over chunks "
            "the vision LLM already extracted at ingest."
        ),
    )
    p_setup.add_argument(
        "--vision-llm",
        default=None,
        metavar="SLUG",
        help=(
            "OpenRouter slug for the vision LLM SurfSense uses at ingest "
            "when --use-vision-llm is on. If omitted in symmetric-cheap / "
            "cost-arbitrage, the strongest registered vision config is "
            "auto-picked (priority: claude-sonnet-4.5 > claude-opus-4.7 > "
            "gpt-5 > gemini-2.5-pro)."
        ),
    )
    p_setup.add_argument(
        "--native-arm-model",
        default=None,
        metavar="SLUG",
        help=(
            "Required for --scenario cost-arbitrage. OpenRouter slug used "
            "by the native_pdf arm only; SurfSense answers with "
            "--provider-model. Ignored for head-to-head / symmetric-cheap."
        ),
    )
    p_setup.add_argument(
        "--no-vision-llm-setup",
        action="store_true",
        help=(
            "Skip attaching a vision LLM config to the SearchSpace even if "
            "the scenario would normally require one. Use when you want to "
            "keep whatever is already attached (e.g. a per-user config)."
        ),
    )
    p_setup.set_defaults(_func=_cmd_setup, _async=True)

    p_teardown = sub.add_parser("teardown", help="Soft-delete the suite SearchSpace + clear state slot.")
    p_teardown.add_argument("--suite", required=True)
    p_teardown.set_defaults(_func=_cmd_teardown, _async=True)

    p_models = sub.add_parser("models", help="LLM-config discovery helpers.")
    models_sub = p_models.add_subparsers(dest="subcommand", required=True)
    p_models_list = models_sub.add_parser("list", help="List global LLM configs.")
    p_models_list.add_argument("--provider", default=None, help="Filter by provider, e.g. openrouter")
    p_models_list.add_argument("--grep", default=None, help="Substring filter on name / model_name.")
    p_models_list.set_defaults(_func=_cmd_models_list, _async=True)

    p_suites = sub.add_parser("suites", help="List registered suites.")
    suites_sub = p_suites.add_subparsers(dest="subcommand", required=True)
    p_suites_list = suites_sub.add_parser("list", help="List suites.")
    p_suites_list.set_defaults(_func=_cmd_suites_list, _async=False)

    p_benchmarks = sub.add_parser("benchmarks", help="List registered benchmarks.")
    bench_sub = p_benchmarks.add_subparsers(dest="subcommand", required=True)
    p_bench_list = bench_sub.add_parser("list", help="List benchmarks.")
    p_bench_list.add_argument("--suite", default=None)
    p_bench_list.set_defaults(_func=_cmd_benchmarks_list, _async=False)

    # Dynamic ingest / run subcommands need the registry populated, so
    # discover up-front (cheap on import — modules just register).
    _discover_suites()

    p_ingest = sub.add_parser("ingest", help="Ingest a benchmark's corpus.")
    ingest_sub = p_ingest.add_subparsers(dest="suite", required=True)
    for suite in registry.list_suites():
        suite_parser = ingest_sub.add_parser(suite, help=f"Ingest a {suite} benchmark.")
        suite_bench = suite_parser.add_subparsers(dest="benchmark", required=True)
        for benchmark in registry.list_benchmarks(suite):
            bp = suite_bench.add_parser(benchmark.name, help=getattr(benchmark, "description", benchmark.name))
            if hasattr(benchmark, "add_run_args"):
                benchmark.add_run_args(bp)
            bp.set_defaults(_func=_cmd_ingest, _async=True)

    p_run = sub.add_parser("run", help="Run a benchmark.")
    run_sub = p_run.add_subparsers(dest="suite", required=True)
    for suite in registry.list_suites():
        suite_parser = run_sub.add_parser(suite, help=f"Run a {suite} benchmark.")
        suite_bench = suite_parser.add_subparsers(dest="benchmark", required=True)
        for benchmark in registry.list_benchmarks(suite):
            bp = suite_bench.add_parser(benchmark.name, help=getattr(benchmark, "description", benchmark.name))
            if hasattr(benchmark, "add_run_args"):
                benchmark.add_run_args(bp)
            bp.set_defaults(_func=_cmd_run, _async=True)

    p_report = sub.add_parser("report", help="Aggregate latest run artifacts into a summary.")
    p_report.add_argument("--suite", required=True)
    p_report.add_argument("--benchmark", default=None, help="Optional: report only this benchmark.")
    p_report.set_defaults(_func=_cmd_report, _async=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    func = getattr(args, "_func", None)
    if func is None:
        parser.print_help()
        return 2
    is_async = getattr(args, "_async", False)
    try:
        if is_async:
            return asyncio.run(func(args))
        return func(args)
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted.[/yellow]")
        return 130
    except Exception as exc:  # noqa: BLE001
        logger.exception("CLI command failed")
        console.print(f"[red]Command failed: {exc}[/red]")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
