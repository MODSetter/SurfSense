# ADR 0011: llama-server in router mode is the one local model runtime

- **Status:** Accepted; the llmfit authoring decision is superseded by [ADR 0026](0026-curated-order-is-list-position.md)
- **Date:** 2026-09-19
- **Supersedes:** the local half of the umbrella plan's "Generation architecture" decision, its "llmfit integration" decision and its "Ollama runtime" decision ([Umbrella plan L107–109](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00-umbrella-plan.md#L107-L109))
- **Source:** [llama.cpp runtime plan L26–38](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/07-llamacpp-runtime.md#L26-L38), [llama.cpp runtime plan L44–49](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/07-llamacpp-runtime.md#L44-L49), [llama.cpp runtime plan L102–116](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/07-llamacpp-runtime.md#L102-L116), [llama.cpp runtime plan L142–148](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/07-llamacpp-runtime.md#L142-L148)

## Context

The local runtime was Ollama. Its library held 240 models. A measured scan resolved 138 of 9,590 llmfit rows to an installable Ollama artifact, 1.4%, and dropped about 1,500 per scan that llama.cpp could run straight from a Hugging Face GGUF. llama.cpp runs anything in GGUF, 204,797 repos on Hugging Face, bounded only by the architectures it supports. It also ships smaller, 11 to 31 MB against Ollama's 501 MB staged payload, fits models to the machine itself with `--fit`, and exposes multimodal and structured-output contracts that Ollama's native API did not. The runtime as built is in [runtime](../architecture/local-models/runtime.md).

## Decision

- One sidecar: `llama-server` in router mode (`--models-dir`, `--models-max 1`). It boots with no model, holds no device memory until one loads, and is one PID for the supervisor to reap ([`sidecars/llamacpp.ts`](../../surfsense_local/electron/src/main/sidecars/llamacpp.ts)).
- Per-model flags go in a preset INI, passed as `--models-preset`, which the router reads once at startup. `POST /models/load` accepts an `args` field and ignores it, measured. Installing a model or changing its load plan rewrites the file, and Electron restarts the sidecar ([`providers/llamacpp/preset.py`](../../surfsense_local/backend/modules/llm/providers/llamacpp/preset.py)).
- `--fit` owns layer placement. SurfSense never sets `n-gpu-layers`: setting it aborts the fitter, and the model then loads entirely on the CPU with exit code 0 and no error.
- MLX is not shipped, to be revisited after launch. MLX's format covers 23,985 Hugging Face repos against GGUF's 204,797. Mac users who want MLX point a connection at LM Studio, which is why the `LM Studio (local)` and `Ollama (local)` presets stay in [`connection-form.tsx`](../../surfsense_local/frontend/src/features/model-selection/connection-form.tsx).
- llmfit runs only at authoring time. A person runs `scripts/refresh_curated_models.py` (now [`scripts/refresh_local_manifest.py`](../../surfsense_local/backend/scripts/refresh_local_manifest.py), which uses no llmfit, per [ADR 0026](0026-curated-order-is-list-position.md)) when adding or changing a curated entry and commits the numbers. llmfit is not shipped, not in CI and not on any request path.

## Consequences

- Apple Silicon loses speed on models under roughly 14B. That is accepted because the LM Studio path already ships and stays on the machine: a loopback endpoint takes no egress decision and needs no key.
- Changing a load plan costs a sidecar restart: about 0.15 s on an idle router, plus reloading the resident model, 10 to 26 s, since the selected model is now loaded at startup and on selection.
- The catalog opens to any GGUF ([ADR 0014](0014-two-tier-model-catalog.md)), fit is computed from the allocator ([ADR 0013](0013-fit-from-the-allocator.md)), and the GPU backend is Vulkan off Apple Silicon ([ADR 0012](0012-vulkan-only-gpu-backend.md)).
- Revision [`0012_llamacpp_provider.py`](../../surfsense_local/backend/alembic/versions/0012_llamacpp_provider.py) clears a generation selection that points at Ollama instead of remapping it, since its weights are in a format the app no longer manages, and turns an `ollama_pull` egress grant into `model_download` only.
- The 2.0.x releases, up to 2.0.2, still ship Ollama. The llama.cpp runtime ([`providers/llamacpp/`](../../surfsense_local/backend/modules/llm/providers/llamacpp/)) is on `dev`, merged in [PR #1819](https://github.com/MODSetter/SurfSense/pull/1819), and ships with the next release.
