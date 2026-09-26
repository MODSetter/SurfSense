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
    # The margin the fitter must leave, in MiB. No default: the badge was drawn
    # against a specific number and the caller always knows which.
    fit_target_mib: int
    mmproj_path: str | None = None


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
        # Pinned rather than inherited. The badge subtracted this margin, so
        # passing it makes the two agree by construction instead of by assuming
        # a default read from the source once.
        f"fit-target = {preset.fit_target_mib}",
        # Inert while `ctx-size` is set: llama.cpp only shrinks a context it
        # chose itself. Written anyway, because it states the floor at the place
        # the fitter would look for one, so a later change to how the window is
        # set cannot quietly hand that floor back to llama.cpp's own 4096.
        f"fit-ctx = {preset.n_ctx}",
    ]
    if preset.mmproj_path is not None:
        # `--fit` does not count the projector, so a vision model the fitter
        # calls resident can still fail to allocate. The margin above carries
        # its bytes; this is what tells the worker to load it at all.
        lines.append(f"mmproj = {preset.mmproj_path}")
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
    # TODO: skip the write when the rendered text matches the file. Every write
    # moves the mtime, Electron's watchGenerationPreset restarts the router on
    # that, and the startup warm_selected() load dies with it, so the first
    # question of every session pays a cold load. Known gap in runtime.md.
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(render_presets(presets))
    temporary.replace(path)
