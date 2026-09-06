import asyncio
import json
import logging
import re
import subprocess
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
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
VERSION_PATTERN = re.compile(r"(\d+\.\d+\.\d+)")


class LlmfitError(RuntimeError):
    def __init__(self, code: str, public_message: str, detail: str = "") -> None:
        super().__init__(detail or public_message)
        self.code = code
        self.public_message = public_message


class LlmfitAdvisor:
    def __init__(
        self,
        executable: Path,
        expected_version: str,
        timeout_seconds: float,
        priority_providers: tuple[str, ...] = (),
    ) -> None:
        self._executable = executable
        self._expected_version = expected_version
        self._timeout_seconds = timeout_seconds
        self._priority_providers = priority_providers

    async def scan(self, max_context: int) -> AdvisorCatalog:
        try:
            version = await self._version()
            if version != self._expected_version:
                return AdvisorCatalog(
                    system=None,
                    models=(),
                    llmfit_version=version,
                    warnings=(
                        RecommendationWarning(
                            "version_mismatch",
                            "Model recommendations are unavailable until llmfit is updated.",
                        ),
                    ),
                )

            system_payload = await self._json("--json", "system")
            fit_payloads = await asyncio.gather(
                self._fit(max_context),
                *(
                    self._fit(max_context, provider)
                    for provider in self._priority_providers
                ),
            )
            system = _parse_system(system_payload)
            models_by_id: dict[str, ScoredModel] = {}
            for payload in fit_payloads:
                for row in _model_rows(payload):
                    model = _parse_model(row)
                    models_by_id.setdefault(model.canonical_id, model)
            models = tuple(models_by_id.values())
            return AdvisorCatalog(system, models, version)
        except LlmfitError as error:
            LOGGER.warning("llmfit scan failed (%s): %s", error.code, error)
            return AdvisorCatalog(
                system=None,
                models=(),
                llmfit_version=None,
                warnings=(RecommendationWarning(error.code, error.public_message),),
            )

    async def _fit(self, max_context: int, provider: str | None = None) -> Any:
        args = [
            "--max-context",
            str(max_context),
            "--json",
            "fit",
        ]
        if provider is not None:
            args.extend(("--providers", provider))
        args.extend(("-n", "1000"))
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
    gguf_sources = row.get("gguf_sources", [])
    estimate_basis = row.get("estimate_basis")

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
        runtime=_code(row.get("runtime")),
        run_mode=_code(row.get("run_mode")),
        best_quant=(
            row.get("best_quant") if isinstance(row.get("best_quant"), str) else None
        ),
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
        ollama_name=(
            row.get("ollama_name") if isinstance(row.get("ollama_name"), str) else None
        ),
        gguf_sources=(
            tuple(item for item in gguf_sources if isinstance(item, str))
            if isinstance(gguf_sources, list)
            else ()
        ),
        notes=(
            tuple(item for item in notes if isinstance(item, str))
            if isinstance(notes, list)
            else ()
        ),
    )
