# ADR 0013: Model fit comes from the allocator's view of one device, and only physics refuses an install

- **Status:** Accepted
- **Date:** 2026-09-19
- **Source:** [llama.cpp runtime plan L52–58](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/07-llamacpp-runtime.md#L52-L58), [llama.cpp runtime plan L95–100](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/07-llamacpp-runtime.md#L95-L100)

## Context

Every installable model build shows a fit badge, and `--fit` decides the real placement at load. The badge is advisory, but it may only err one way. An over-estimate costs a pessimistic badge on a model that installs anyway; an under-estimate ships a confident badge about a model that spills, which is the failure the estimator exists to remove. Machines also report memory in misleading ways: the same card appears once per loaded backend, an integrated GPU can advertise more memory than a discrete one, and Apple Silicon reports two views of one memory. Fit as built is in [fit](../architecture/local-models/fit.md).

## Decision

- Device memory comes from `ggml_backend_dev_memory()`, the allocator's own view, called through `ctypes` in a child process ([`hardware/probe_subprocess.py`](../../surfsense_local/backend/modules/llm/hardware/probe_subprocess.py)). The child exists because ggml's backend scan keys on the running executable's directory, because a driver fault would otherwise take the API down with it, and because the first Metal device query compiles 20 shader libraries in 19 seconds. The model's side comes from its GGUF header.
- The budget is one device: the first device ggml types as GPU, never a sum ([`hardware/selection.py`](../../surfsense_local/backend/modules/llm/hardware/selection.py)). An integrated GPU measured 16198 MiB against a discrete card's 6002 MiB, so "largest" is wrong too. ggml already orders backends by preference, so taking the first is also backend selection.
- Two numbers, never one overhead term: `resident_bytes`, what the model must fit inside to run at full speed, and `refusal_bytes`, what physics allows at all ([`fit/budget.py`](../../surfsense_local/backend/modules/llm/fit/budget.py)). Collapsing them predicted residency for a configuration that measurably spilled, wrong by 922 MiB (recorded 21 Sep 2026).
- Unified memory is one pool, `min(working set, 0.85 × host)` ([`hardware/unified_pool.py`](../../surfsense_local/backend/modules/llm/hardware/unified_pool.py)). Summed, an 8 GB Mac priced as though it had 10.3 GB (recorded 21 Sep 2026).
- Only physics refuses. `can_install` is `state is not TOO_BIG`, and `PARTIAL` installs exactly like `FITS`. Eligibility (architecture, chat template, gated repo) blocks separately and is not a fit state.
- Context is fixed at load: a floor of 8192, rungs of 8192, 16384 and 32768, capped at the model's own `context_length` ([`fit/plan_load.py`](../../surfsense_local/backend/modules/llm/fit/plan_load.py)) (recorded 21 Sep 2026; the 19 Sep plan had a 16K floor).
- The KV cache is `f16` when it fits, and `q8_0` only when that turns a spill into residency. One rule in [`fit/precision.py`](../../surfsense_local/backend/modules/llm/fit/precision.py) is read by both the badge and the loader.

## Consequences

- The badge and the load plan cannot describe different configurations of the same model.
- A model that spills still installs, and its badge says it runs at reduced speed.
- `q8_0` depends on a working flash-attention kernel; without one, llama.cpp falls back to CPU attention silently. That dependency is taken only where it buys residency, and whether it is the right trade at all is still an open measurement.
- The first device probe on a Mac takes about 19 seconds, so the API warms the catalog on a background thread at startup instead of holding back `/health` ([`api/main.py`](../../surfsense_local/backend/api/main.py)).
