"""The llmfit adapter: shells out to the pinned binary and caches its verdict.

This is the only module that knows llmfit's CLI/JSON contract. Everything
above `LlmfitAdvisor` (CatalogService and up) only ever sees `ScoredModel`/
`SystemProfile`/`AdvisorCatalog` — plain, versioned dataclasses, not llmfit's
own vocabulary. That seam is what lets the cache live here too: the cache's
job is "did we already ask llmfit this exact question," which only this
module has enough context to answer.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from modules.llm.recommendations.types import (
    AdvisorCatalog,
    FitLevel,
    RecommendationWarning,
    ScoredModel,
    SystemProfile,
)

LOGGER = logging.getLogger(__name__)
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
VERSION_PATTERN = re.compile(r"(\d+\.\d+\.\d+)")

# Bumped whenever ScoredModel's shape changes. A mismatch discards the cache
# file and rescans: a cached row is an optimisation, never something worth
# migrating.
CACHE_VERSION = 1

# Tuple fields survive a JSON round-trip as lists.
_TUPLE_FIELDS = ("capability_ids", "gguf_sources", "notes")


class LlmfitError(RuntimeError):
    def __init__(self, code: str, public_message: str, detail: str = "") -> None:
        super().__init__(detail or public_message)
        self.code = code
        self.public_message = public_message


class LlmfitAdvisor:
    """Scores models with the pinned llmfit binary and caches the result.

    The cache lives here rather than in CatalogService because its fingerprint
    needs the hardware profile, and nothing above this seam should re-derive
    it. `scan(refresh=False)` never spawns the expensive per-model scoring
    subprocess — it only ever answers from a fingerprint-matched cache file,
    or reports "not scanned" so the caller can decide what to show instead.
    Only `refresh=True` (an explicit user action) pays that cost and refreshes
    the cache.
    """

    def __init__(
        self,
        executable: Path,
        expected_version: str,
        timeout_seconds: float,
        priority_providers: tuple[str, ...] = (),
        *,
        cache_path: Path | None = None,
    ) -> None:
        self._executable = executable
        self._expected_version = expected_version
        self._timeout_seconds = timeout_seconds
        self._priority_providers = priority_providers
        self._cache_path = cache_path

    async def scan(self, max_context: int, *, refresh: bool = False) -> AdvisorCatalog:
        # Tier 1 is fatal: without a version and a hardware profile there is
        # nothing to score against and no fingerprint to key a cache on.
        try:
            version = await self._version()
            if version != self._expected_version:
                return AdvisorCatalog(
                    system=None,
                    models=(),
                    llmfit_version=version,
                    scanned=True,
                    warnings=(
                        RecommendationWarning(
                            "version_mismatch",
                            "Model recommendations are unavailable until llmfit is updated.",
                        ),
                    ),
                )
            system = _parse_system(await self._json("--json", "system"))
        except LlmfitError as error:
            LOGGER.warning("llmfit probe failed (%s): %s", error.code, error)
            return AdvisorCatalog(
                system=None,
                models=(),
                llmfit_version=None,
                scanned=True,
                warnings=(RecommendationWarning(error.code, error.public_message),),
            )

        fingerprint = _fingerprint(version, system, max_context)
        if not refresh:
            cached = self._read_cache(fingerprint)
            if cached is not None:
                return AdvisorCatalog(system, cached, version, scanned=True)
            # No cache for this exact hardware/version/context yet, and this
            # call wasn't an explicit "scan now" — never spawn the expensive
            # subprocess implicitly. The caller shows scan-free content
            # instead (installed + curated) and offers a "Scan hardware"
            # action, which comes back through here with refresh=True.
            return AdvisorCatalog(system, (), version, scanned=False)

        try:
            fit_payloads = await asyncio.gather(
                self._fit(max_context),
                *(
                    self._fit(max_context, provider)
                    for provider in self._priority_providers
                ),
            )
        except LlmfitError as error:
            LOGGER.warning("llmfit scan failed (%s): %s", error.code, error)
            return AdvisorCatalog(
                system=system,
                models=(),
                llmfit_version=version,
                scanned=True,
                warnings=(RecommendationWarning(error.code, error.public_message),),
            )

        models_by_id: dict[str, ScoredModel] = {}
        for payload in fit_payloads:
            for row in _model_rows(payload):
                model = _parse_model(row)
                models_by_id.setdefault(model.canonical_id, model)
        models = tuple(models_by_id.values())
        self._write_cache(fingerprint, models)
        return AdvisorCatalog(system, models, version, scanned=True)

    async def _fit(self, max_context: int, provider: str | None = None) -> Any:
        args = [
            "--max-context",
            str(max_context),
            "--json",
            "fit",
        ]
        if provider is not None:
            args.extend(("--providers", provider))
        return await self._json(*args)

    async def _version(self) -> str:
        output = await self._run("--version")
        match = VERSION_PATTERN.search(output)
        if match is None:
            raise LlmfitError(
                "invalid_output",
                "Model recommendations are temporarily unavailable.",
                "llmfit --version returned no semantic version",
            )
        return match.group(1)

    async def _json(self, *args: str) -> Any:
        output = await self._run(*args)
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise LlmfitError(
                "invalid_output",
                "Model recommendations are temporarily unavailable.",
                f"invalid llmfit JSON: {error}",
            ) from error

    async def _run(self, *args: str) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                str(self._executable),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=MAX_OUTPUT_BYTES,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError as error:
            raise LlmfitError(
                "missing",
                "Hardware recommendations are unavailable because llmfit is missing.",
            ) from error
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout_seconds
            )
        except TimeoutError as error:
            process.kill()
            await process.wait()
            raise LlmfitError(
                "timeout",
                "Hardware detection took too long. Try rescanning.",
            ) from error

        if len(stdout) > MAX_OUTPUT_BYTES or len(stderr) > MAX_OUTPUT_BYTES:
            raise LlmfitError(
                "invalid_output",
                "Model recommendations returned too much data.",
            )
        if process.returncode != 0:
            detail = stderr.decode(errors="replace").strip()
            raise LlmfitError(
                "scan_failed",
                "Hardware recommendations could not be calculated.",
                detail,
            )
        return stdout.decode().strip()

    def _read_cache(
        self, fingerprint: dict[str, Any]
    ) -> tuple[ScoredModel, ...] | None:
        """Cached rows for this exact fingerprint, or None to rescan.

        Every failure mode is "slower", never "broken": a missing, truncated,
        stale or unreadable file just means no cache hit.
        """
        if self._cache_path is None:
            return None
        try:
            document = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if document.get("cache_version") != CACHE_VERSION:
                return None
            if document.get("fingerprint") != fingerprint:
                return None
            return tuple(_model_from_json(row) for row in document["models"])
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError, KeyError) as error:
            LOGGER.warning("discarding unreadable llmfit cache: %s", error)
            return None

    def _write_cache(
        self, fingerprint: dict[str, Any], models: tuple[ScoredModel, ...]
    ) -> None:
        if self._cache_path is None or not models:
            return
        document = {
            "cache_version": CACHE_VERSION,
            "fingerprint": fingerprint,
            "scanned_at": datetime.now(UTC).isoformat(),
            "models": [_model_to_json(model) for model in models],
        }
        # Rename onto the final path so an interrupted multi-megabyte write
        # cannot leave JSON that parses as garbage.
        temporary = self._cache_path.with_suffix(".json.tmp")
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(document), encoding="utf-8")
            os.replace(temporary, self._cache_path)
        except OSError as error:
            LOGGER.warning("could not write llmfit cache: %s", error)
            temporary.unlink(missing_ok=True)


def _fingerprint(
    version: str, system: SystemProfile, max_context: int
) -> dict[str, Any]:
    """The inputs a scan was run against. Stored as fields, not a hash, so an
    unexpected invalidation can be read straight out of the cache file."""
    return {
        "llmfit_version": version,
        "gpu_name": system.gpu_name,
        "gpu_vram_gb": system.gpu_vram_gb,
        "gpu_count": system.gpu_count,
        "total_ram_gb": system.total_ram_gb,
        "cpu_name": system.cpu_name,
        "cpu_cores": system.cpu_cores,
        "backend": system.backend,
        "max_context": max_context,
    }


def _model_to_json(model: ScoredModel) -> dict[str, Any]:
    data = asdict(model)
    data["fit"] = model.fit.value
    return data


def _model_from_json(data: dict[str, Any]) -> ScoredModel:
    data = dict(data)
    data["fit"] = FitLevel(data["fit"])
    for name in _TUPLE_FIELDS:
        data[name] = tuple(data.get(name) or ())
    return ScoredModel(**data)


def _code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _integer(value: Any) -> int | None:
    return int(value) if isinstance(value, int | float) else None


def _parse_system(payload: Any) -> SystemProfile:
    if not isinstance(payload, dict) or not isinstance(payload.get("system"), dict):
        raise LlmfitError(
            "invalid_output",
            "Hardware recommendations returned an unsupported system profile.",
        )
    row = payload["system"]
    return SystemProfile(
        cpu_name=row.get("cpu_name") if isinstance(row.get("cpu_name"), str) else None,
        cpu_cores=_integer(row.get("cpu_cores")),
        total_ram_gb=_number(row.get("total_ram_gb")),
        available_ram_gb=_number(row.get("available_ram_gb")),
        has_gpu=bool(row.get("has_gpu", False)),
        gpu_name=row.get("gpu_name") if isinstance(row.get("gpu_name"), str) else None,
        gpu_vram_gb=_number(row.get("gpu_vram_gb")),
        gpu_count=_integer(row.get("gpu_count")) or 0,
        backend=row.get("backend") if isinstance(row.get("backend"), str) else None,
        unified_memory=bool(row.get("unified_memory", False)),
    )


def _model_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise LlmfitError(
            "invalid_output",
            "Model recommendations returned an unsupported catalog.",
        )
    if not all(isinstance(row, dict) for row in payload["models"]):
        raise LlmfitError(
            "invalid_output",
            "Model recommendations contained an invalid model entry.",
        )
    return payload["models"]


def _gguf_sources(value: Any) -> tuple[str, ...]:
    """Hugging Face GGUF repos llmfit found for this model.

    Real llmfit output is a list of `{"provider": ..., "repo": ...}` dicts,
    not bare strings — this is the repo half of each one, which is all a
    runtime needs to build an `hf.co/<repo>` pull target from.
    """
    if not isinstance(value, list):
        return ()
    repos: list[str] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("repo"), str):
            repos.append(item["repo"])
    return tuple(repos)


def _fallback_ollama_name(
    gguf_sources: tuple[str, ...], runtime: str | None, best_quant: str | None
) -> str | None:
    """`hf.co/<repo>[:<quant>]` for a model Ollama's own library doesn't have.

    Ollama can pull any GGUF straight from Hugging Face this way. The quant
    suffix is only trustworthy when llmfit scored the model against
    `llama_cpp` specifically: on other runtimes (e.g. `mlx`, only ever seen
    on Apple Silicon, where MLX beats llama.cpp) `best_quant` is a label in
    that runtime's own vocabulary (`mlx-4bit`), not a GGUF file suffix, and
    would make the pull fail. Without a trusted quant, Ollama's own default
    for an untagged `hf.co/...` pull is to prefer `Q4_K_M` when present in
    the repo, else one reasonable quant — a sane fallback, not a guess.

    The tag is always explicit, never omitted: a bare `hf.co/<repo>` pull
    request is accepted by Ollama, but it silently stores the result as
    `hf.co/<repo>:latest` (confirmed against a real pull) — every later
    exact-string match against this `ollama_name` (install verification,
    "already installed" detection on a rescan) would then permanently fail
    against an identifier that never matches what Ollama actually named it.
    Requesting `:latest` up front keeps the string we hand out identical to
    what comes back.
    """
    if not gguf_sources:
        return None
    repo = gguf_sources[0]
    if runtime == "llama_cpp" and best_quant:
        return f"hf.co/{repo}:{best_quant}"
    return f"hf.co/{repo}:latest"


def _parse_model(row: dict[str, Any]) -> ScoredModel:
    name = row.get("name")
    if not isinstance(name, str) or not name.strip():
        raise LlmfitError(
            "invalid_output",
            "Model recommendations contained a model without an id.",
        )
    fit_code = _code(row.get("fit_level"))
    try:
        fit = FitLevel(fit_code)
    except (TypeError, ValueError):
        fit = FitLevel.UNKNOWN

    publisher = row.get("provider")
    publisher = publisher if isinstance(publisher, str) else None
    display = name.rsplit("/", 1)[-1]
    family = display.split("-", 1)[0] or display
    capabilities = row.get("capability_ids", row.get("capabilities", []))
    capability_ids = (
        tuple(code for item in capabilities if (code := _code(item)))
        if isinstance(capabilities, list)
        else ()
    )
    notes = row.get("notes", [])
    estimate_basis = row.get("estimate_basis")
    runtime = _code(row.get("runtime"))
    best_quant = (
        row.get("best_quant") if isinstance(row.get("best_quant"), str) else None
    )
    gguf_sources = _gguf_sources(row.get("gguf_sources"))

    native_ollama_name = row.get("ollama_name")
    native_ollama_name = (
        native_ollama_name if isinstance(native_ollama_name, str) else None
    )
    ollama_name = native_ollama_name or _fallback_ollama_name(
        gguf_sources, runtime, best_quant
    )
    # A fallback pull's fit badge must not overstate confidence: it's honest
    # only when the quant used to build the pull target is the same one the
    # fit/memory numbers above were computed for (the `runtime == "llama_cpp"`
    # case in `_fallback_ollama_name`). Otherwise the badge describes a
    # different runtime's memory profile than the file Ollama will actually
    # fetch — relabel to Marginal (a hedge, not a promise) rather than either
    # hiding the model entirely or carrying forward a number that doesn't
    # match what gets installed.
    trusted_quant = native_ollama_name is not None or runtime == "llama_cpp"
    if native_ollama_name is None and gguf_sources and not trusted_quant:
        fit = FitLevel.MARGINAL

    return ScoredModel(
        canonical_id=name,
        publisher=publisher,
        family=family,
        display_name=display,
        parameter_count=(
            row.get("parameter_count")
            if isinstance(row.get("parameter_count"), str)
            else None
        ),
        params_b=_number(row.get("params_b")),
        use_case=_code(row.get("use_case") or row.get("category")),
        fit=fit,
        score=_number(row.get("score")),
        runtime=runtime,
        run_mode=_code(row.get("run_mode")),
        best_quant=best_quant,
        memory_required_gb=_number(row.get("memory_required_gb")),
        memory_available_gb=_number(row.get("memory_available_gb")),
        utilization_pct=_number(row.get("utilization_pct")),
        disk_size_gb=_number(row.get("disk_size_gb")),
        estimated_tps=_number(row.get("estimated_tps")),
        prefill_tps=_number(row.get("prefill_tps")),
        ttft_ms=_number(row.get("ttft_ms")),
        estimate_confidence=_code(row.get("estimate_confidence")),
        estimate_basis=estimate_basis if isinstance(estimate_basis, dict) else None,
        effective_context_length=_integer(row.get("effective_context_length")),
        capability_ids=capability_ids,
        license=row.get("license") if isinstance(row.get("license"), str) else None,
        ollama_name=ollama_name,
        gguf_sources=gguf_sources,
        notes=(
            tuple(item for item in notes if isinstance(item, str))
            if isinstance(notes, list)
            else ()
        ),
    )
