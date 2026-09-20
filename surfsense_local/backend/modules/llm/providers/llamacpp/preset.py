"""Per-model launch arguments, written where the router will read them.

`POST /models/load` takes an `args` field that does nothing. Measured at b11050
on macOS: `{"args": ["-c","4096"]}`, `{"args": ["--ctx-size","4096","-fa","on"]}`
and `{"preset": "..."}` all return `200 {"success":true}` while the spawned
worker's argv stays byte identical. `--models-preset <ini>` is the mechanism
that works, so this module is the seam between the fit calculation and the
runtime.

The file is read once, at router startup. Adding a section while the router runs
does not surface the model, so installing one means rewriting this and
restarting the sidecar.
"""

from dataclasses import dataclass
from pathlib import Path

from modules.llm.fit import KvPrecision

# The name Electron watches for changes and passes as `--models-preset`. Both
# sides have to agree on it, so it is stated once here.
PRESET_FILE = "models.ini"


@dataclass(frozen=True)
class ModelPreset:
    """What the fit calculation decided for one model."""

    model_id: str
    path: str
    n_ctx: int
    precision: KvPrecision


def render_presets(presets: list[ModelPreset]) -> str:
    """The INI text. One section per model, keyed by the id the router reports.

    Deliberately absent: any layer count. Setting `n_gpu_layers` by hand aborts
    `--fit`, after which llama.cpp loads the model entirely on the CPU with no
    error and exit 0. `--fit` owns placement; we only tell it how much to place.
    """
    return "\n".join(_section(p) for p in presets)


def _section(preset: ModelPreset) -> str:
    lines = [
        f"[{preset.model_id}]",
        f"model = {preset.path}",
        f"ctx-size = {preset.n_ctx}",
        # One user, one question. The default of four sizes the KV cache for
        # concurrency this app never uses.
        "parallel = 1",
    ]
    if preset.precision is KvPrecision.Q8_0:
        # Both halves together, or the fused flash-attention kernel is skipped
        # and attention silently falls back to the CPU.
        lines += [
            "cache-type-k = q8_0",
            "cache-type-v = q8_0",
            "flash-attn = on",
        ]
    return "\n".join(lines) + "\n"


def write_presets(path: Path, presets: list[ModelPreset]) -> None:
    """Replace the preset file atomically, so a half-written INI never loads."""
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(render_presets(presets))
    temporary.replace(path)
