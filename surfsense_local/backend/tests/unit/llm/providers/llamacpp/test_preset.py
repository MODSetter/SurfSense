"""The INI the router reads per-model arguments from.

`POST /models/load` accepts an `args` field and ignores it: measured at b11050,
every payload shape returns 200 while the worker's argv stays byte identical.
`--models-preset` is the mechanism that works, so this file is where the fit
calculation reaches the runtime.
"""

import pytest

from modules.llm.fit import KvPrecision
from modules.llm.providers.llamacpp import ModelPreset, render_presets

pytestmark = pytest.mark.unit


def a_preset(**overrides) -> ModelPreset:
    """A resident 8B at the context floor unless a test says otherwise."""
    fields = {
        "model_id": "Qwen3-8B-Q4_K_M",
        "path": "/models/Qwen3-8B-Q4_K_M.gguf",
        "n_ctx": 16384,
        "precision": KvPrecision.F16,
    }
    return ModelPreset(**{**fields, **overrides})


def test_the_window_the_fit_calculation_chose_reaches_the_worker() -> None:
    """The whole point: llama.cpp would otherwise use the model's own default,
    and would shrink it to 4096 on its own if we left it unset."""
    ini = render_presets([a_preset(n_ctx=24576)])

    assert "ctx-size = 24576" in ini


def test_a_section_is_named_for_the_model_it_configures() -> None:
    """The router matches sections by the id it reports for a discovered file."""
    ini = render_presets([a_preset()])

    assert "[Qwen3-8B-Q4_K_M]" in ini
    assert "model = /models/Qwen3-8B-Q4_K_M.gguf" in ini


def test_quantized_cache_sets_both_halves_and_turns_on_flash_attention() -> None:
    """A mismatched pair silently falls back to an unoptimised path, and quantized
    cache without a working fused kernel collapses to CPU attention with no
    warning at all. Both halves, or neither."""
    ini = render_presets([a_preset(precision=KvPrecision.Q8_0)])

    assert "cache-type-k = q8_0" in ini
    assert "cache-type-v = q8_0" in ini
    assert "flash-attn = on" in ini


def test_an_unquantized_cache_names_no_cache_type_at_all() -> None:
    """f16 is llama.cpp's default, and naming it would take on the flash-attention
    dependency for nothing."""
    ini = render_presets([a_preset(precision=KvPrecision.F16)])

    assert "cache-type" not in ini


def test_every_model_is_pinned_to_one_slot() -> None:
    """llama-server defaults to four parallel slots and sizes the KV cache for
    all of them. This app has one user asking one question."""
    assert "parallel = 1" in render_presets([a_preset()])


def test_several_models_each_get_their_own_section() -> None:
    """One installed model must not inherit another one's window."""
    ini = render_presets(
        [a_preset(), a_preset(model_id="Qwen3-4B-Q4_K_M", path="/models/4b.gguf")]
    )

    assert ini.count("ctx-size") == 2
    assert "[Qwen3-4B-Q4_K_M]" in ini


def test_no_explicit_layer_count_is_ever_written() -> None:
    """Setting n_gpu_layers by hand aborts --fit, after which the model loads
    entirely on the CPU with no error and exit 0. It looks like it worked."""
    ini = render_presets([a_preset()])

    assert "n-gpu-layers" not in ini
    assert "ngl" not in ini
