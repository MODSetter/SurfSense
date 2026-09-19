# API — Phase 7: Replace Ollama with llama.cpp

> Owns: `modules/llm/providers/`, the runtime sidecar, the model catalog, and
> packaging for all three targets. Supersedes the Ollama runtime decision in
> [`../00-umbrella-plan.md`](../00-umbrella-plan.md) and the `hf.co/` fallback in
> [`05d-llmfit-catalog-expansion.md`](05d-llmfit-catalog-expansion.md). Extends
> [`05a-model-recommendations.md`](05a-model-recommendations.md) — its
> "llama.cpp, later" section is now this document.

## Goal

One local runtime: `llama-server` in router mode. Any GGUF model the user wants,
not a curated subset. Recommendations that come from the machine's own allocator
rather than an advisor's estimate.

Ingestion, the 384-dimensional bge-small index, retrieval, and chat SSE do not
change.

## Why

Ollama's library holds 240 models. A measured scan on this branch resolved 138
of 9,590 llmfit rows to an installable Ollama artifact — 1.4%. The
`ollama_name` gate in `OllamaRuntime.resolve()` drops every model Ollama's own
registry does not carry, including the ~1,500 per scan that llama.cpp could run
directly from a Hugging Face GGUF.

llama.cpp runs anything in GGUF: **204,797 repos on Hugging Face**, bounded only
by its 152 supported architectures. The runtime also ships smaller (11–31 MB
versus Ollama's 501 MB staged payload), fits models to the machine itself
(`--fit`, default on), and exposes multimodal and structured-output contracts
Ollama's native API does not.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| **Runtime** | `llama-server` router mode, single sidecar | `--models-dir`, `--models-max 1`, LRU eviction, one PID for the supervisor to reap. Maps 1:1 onto every Ollama call the adapter makes. |
| **MLX** | **Not shipped.** Revisit after launch | Ollama switched its Apple Silicon engine to MLX in Mar 2026, so the swap costs Mac speed on models under ~14B. MLX's format covers 23,985 HF repos against GGUF's 204,797 — one format and the full catalog wins. Mac users who want MLX point a connection at LM Studio; see **The Mac path**. |
| **llmfit** | **Build-time only. Not shipped.** | It ranks the curated entries in CI and writes the numbers into the manifest. It is not a gate, not a hardware source, and not in any request path. Removes 27 MB, a pinned version, and five failure modes per installer. |
| **Gating** | Only physics refuses | Weights + minimum KV exceeding VRAM **plus** RAM. `can_install` never reads a fit level. Everything else is a badge. |
| **Catalog** | Two tiers — curated manifest, and Hugging Face search | Curated is the offline product and ships frozen. Search is a network feature that is simply absent airgapped. |
| **Fit estimate** | Our own, from the GGUF header | llmfit cannot score a model outside its database (`llmfit plan` states the precondition). Search needs an estimate anyway; once it exists, llmfit's is redundant *and* less accurate here. |
| **Hardware budget** | `ggml_backend_dev_memory()` via `ctypes`, from the shipped libs | The allocator's own view. Falls back to `llama-server --list-devices`, then OS APIs. |
| **Downloads** | **SurfSense fetches the GGUF**, not `POST /models` | `llama-server` is a second process we do not proxy; an in-process fetch is the only place `egress.require()` actually holds. Also buys resume, checksums, and the header as the file lands. |
| **Quantization** | Pinned per entry; two variants on the two largest | A pinned file is what "tested by SurfSense" can honestly claim. See **The quantization ladder**. |
| **Context** | Set at load, grown on occupancy. Floor 16K | llama.cpp fixes context at load; `num_ctx()`'s per-request sizing has no equivalent. 3K history + ~8K grounding + reply. |
| **Windows CUDA** | **In the installer.** No post-install download | Airgapped. Dropping Ollama frees ~500 MB; CUDA 13.4 + cudart costs 573 MB. Net ≈ +100 MB, under the 2 GB `makensis` ceiling that forced `pruneCudaRunners()`. |
| **CUDA version** | 13.4 only | CUDA 13 requires Turing (7.5)+. Shipping 12.4 as well for Pascal costs another 645 MB — that is what made Ollama's archive 1.8 GB. Pascal falls through to Vulkan automatically via backend scoring. |
| **Backend selection** | Runtime, by ggml | Releases are built `GGML_BACKEND_DL=ON`. A failed `dlopen` is skipped silently, so a missing Vulkan loader degrades to CPU rather than failing. |
| **Prompt tier fallback** | Keys on **loopback**, not provider name | `provider == "ollama" → COMPACT` breaks the moment a Mac user runs a 4B through LM Studio. `host_destination()` already computes loopback. |

## Boundaries

```text
  hardware budget ── ggml_backend_dev_memory()  ← the allocator, not an advisor
         │
  model facts ───── GGUF header (local file, or HTTP Range on huggingface.co)
         │
         ▼
  FitEstimator ── advisory only
         │          weights + KV(window) + overhead  vs  VRAM + RAM
         │          → fits-gpu | needs-ram | too-big | PhysicsRefusal
         ▼
  CatalogService
     ├── curated   manifest, ranked by llmfit AT BUILD TIME, ships frozen
     └── search    HF /api/models?filter=gguf  +  /tree/main
         │
         ▼
  LlamaCppProvider ── Generator + ModelStore + LocalRuntime
         │
         ▼
  llama-server router ── --fit places layers; the real answer
```

The estimator is advisory at every stage above the runtime. `--fit`'s allocation
is authoritative at launch, and generation is ground truth after it. Unknown
shapes round **up**; never underestimate memory.

## The quantization ladder

Measured: architecture fields are identical across quantizations of the same
model (`Q4_K_M`, `Q8_0`, `f16` of SmolLM2-135M all report `layers=30
kv_heads=3 emb=576 ctx=8192`; only `general.file_type` differs). KV cost is
architecture-derived and quant-independent. So **one header read prices every
quantization of a model**, and the weights bytes come free from `tree/main`.

Per-machine quant selection is therefore possible at no extra cost. We pin
anyway, for three reasons that are policy rather than capability: the
"tested by SurfSense" claim covers files we ran, support needs reproducible
bytes, and an unconstrained fit-maximiser hands small machines a Q2_K build
that answers noticeably worse (llmfit currently recommends exactly that for
Qwen3-14B on an 8 GB Mac).

The shipped eight, measured at Q4_K_M and a 16K window:

| model | file GB | layers | kv_heads | needs @16K |
|---|---|---|---|---|
| Qwen3 0.6B | 0.40 | 28 | 8 | 2,354 MiB |
| Qwen3 1.7B | 1.11 | 28 | 8 | 3,032 |
| Qwen3 4B | 2.50 | 36 | 8 | 4,630 |
| Qwen2.5-Coder 7B | 4.68 | 28 | 4 | 5,966 |
| Qwen3 8B | 5.03 | 36 | 8 | 7,043 |
| Qwen3 14B | 9.00 | 40 | 8 | 10,969 |
| Qwen3 32B | 19.76 | 64 | 8 | 22,047 |
| Qwen2.5-Coder 32B | 19.85 | 64 | 8 | 22,132 |

What each machine gets:

```text
machine          0.6B 1.7B  4B  C7B  8B  14B  32B C32B   →  recommended
M2 8 GB           GPU  GPU GPU  RAM RAM  RAM    —    —   →  Qwen3 4B     (831 MiB spare)
RTX 3050 6 GB     GPU  GPU GPU  RAM RAM  RAM  RAM  RAM   →  Qwen3 4B     (490 MiB spare)
M4 16 GB          GPU  GPU GPU  GPU GPU  RAM  RAM  RAM   →  Qwen3 8B   (3,857 MiB spare)
RTX 4070 12 GB    GPU  GPU GPU  GPU GPU  GPU  RAM  RAM   →  Qwen3 14B     (31 MiB spare)
RTX 4090 24 GB    GPU  GPU GPU  GPU GPU  GPU  GPU  GPU   →  Qwen3 32B    (953 MiB spare)
M4 Max 64 GB      GPU  GPU GPU  GPU GPU  GPU  GPU  GPU   →  Qwen3 32B  (26,000 MiB spare)
```

Every machine gets a GPU-resident pick, so eight rungs strand nobody. Three gaps:

- **The top collapses.** 24 GB and 64 GB — 2.7× apart — get the same file, and
  the larger wastes 26 GB. A higher quant does not fix this; 32B at Q8 is ~35 GB
  and still leaves room. **The top needs a bigger model.**
- **A gap at 16 GB.** 14B misses by 69 MiB (0.6%), so a 16 GB Mac drops to 8B
  with 3.9 GB spare.
- **The 4070 row is decided by an uncalibrated constant.** 31 MiB of margin at
  1,024 MiB overhead; at Hermes' measured 1.5 GiB it does not fit and that
  machine drops a rung.

Manifest changes, in priority order:

1. **A rung above 32B** — an 80B-A3B-class MoE. The only thing that serves
   48–64 GB machines. MoE needs a `decode_fraction` field (active bytes read per
   token) or the speed prediction is wrong by an order of magnitude.
2. **A second variant on 8B and 32B** (`Q6_K`), filling the 16 GB gap and giving
   the 4090 somewhere to go. Two extra pins, not fifty.
3. **A vision entry.** All eight are text-only, in an app with a PDF pipeline.
4. **Calibrate the overhead constant** before shipping. It decides the 4070 row.

## The Mac path

Dropping Ollama costs Apple Silicon speed on models under ~14B. Accepted,
because the escape hatch already ships and does not leave the machine:

- `host_destination()` returns `None` for loopback — *"nothing leaves the
  machine"* — so `require()` no-ops and no egress prompt appears.
- `api_key_ciphertext` is nullable and `_headers(None)` returns `{}` — keyless
  local endpoints work end to end.
- `connection-form.tsx` already ships `LM Studio (local) → http://localhost:1234/v1`
  and `Ollama (local) → http://localhost:11434/v1`.

LM Studio runs MLX on Apple Silicon. A Mac user who wants it installs LM Studio
and picks the preset. **Keep the Ollama preset** — it is the user-managed MLX
path now, not dead code.

## Runtime contract

| Ollama today | llama-server router |
|---|---|
| `GET /` | `GET /health` |
| `GET /api/tags` | `GET /models` (+ `architecture.input_modalities`) |
| `POST /api/show` | `GET /props?model=…` — `chat_template_caps`, `modalities`, `n_ctx` |
| `POST /api/pull` | we fetch `resolve/main/{file}` ourselves |
| blob cleanup on cancel | **deleted** — `cleanup_cancelled_download()`, ~40 lines |
| `DELETE /api/delete` | `DELETE /models?model=…` |
| `POST /api/chat` | `POST /v1/chat/completions` — compose `OpenAICompatibleChatProvider` |

Sidecar flags: `--models-dir <dataDir>/models --port <free> --models-max 1
--sleep-idle-seconds 300 --no-ui --jinja --reasoning-format deepseek`.

`--no-ui` because llama-server ships its own web UI. `--reasoning-format deepseek`
routes `<think>` blocks to `message.reasoning_content`; without it a thinking
model's trace enters `parts[]` and `resolve_citations()` rewrites `[n]` tokens
that appeared inside the reasoning.

## Phases

Phases 7.0–7.5 keep Ollama registered and working. `REGISTRY` carries both
adapters, so each ships independently and is reversible. **7.6 is the only
irreversible phase and the only one that touches user data.**

### 7.0 — De-Ollama the domain

No runtime change. `ScoredModel.ollama_name` → `artifacts: tuple[GgufArtifact, ...]`
where `GgufArtifact(repo, quantization, mmproj)`. `OllamaProvider` renders
`hf.co/{repo}:{quant}` itself, so the runtime's private vocabulary stops leaking
upward.

Deleted: `_fallback_ollama_name()`, `clean_runtime_name()`, the `trusted_quant`
gate, the `FitLevel.MARGINAL` relabel, the `:latest` workaround. All five exist
only because Ollama's library was in the way.

llmfit adapter switches to `recommend --force-runtime llamacpp --output-llamacpp
-n <bulk> --no-dashboard`. Bump `CACHE_VERSION`.

**Tests:** `llmfit.py` fixtures. No UI change.

### 7.1 — GGUF header reader

`modules/llm/gguf/header.py`, stdlib only. Local file or `Range: bytes=0-4194303`
against `huggingface.co`. Yields architecture, `block_count`, `context_length`,
`embedding_length`, `head_count_kv`, key/value lengths, `sliding_window`,
`expert_count`, `n_vocab`, chat template, exact tensor bytes.

Verified: HF returns `206` with `accept-ranges: bytes`. A 135M model's metadata
ends at 1.77 MB and its tensor table at 1.79 MB, in 2.5 s. Budget 4 MB and
retry wider on a truncated parse — the vocab token list is what makes it large.

**Tests:** a checked-in truncated GGUF; a fake HTTP server asserting the Range
header and a truncated-response retry.

### 7.2 — Hardware budget and estimator

`modules/llm/hardware.py` — `ctypes` into `libggml`, then `--list-devices`, then
OS APIs. First hit wins, cached; warm the probe in the background at first
launch, not on the path of the first render (a cold `ggml_backend_load_all()` on
macOS compiles 20 Metal shader libraries, measured at ~20 s once, 180 ms after).

Two budget modes. **Capacity** (total − margin) for catalog pricing; **live**
(free now) for launch decisions. Pricing against live-free while a model is
loaded makes every row read as too large.

`modules/llm/fit.py` — `weights + KV(window) + overhead` vs `VRAM + RAM`.
Per-layer KV from the header. Split today's single `recommendation_reserve_gb: 2.0`
(flagged `ponytail` as uncalibrated) into a measured runtime overhead, a device
margin, and a UMA headroom.

> **ponytail:** the runtime overhead constant is a placeholder until measured
> against real RSS on all three targets. On a 5.4 GB budget it moves rows across
> the fits/spills line.

**Tests:** decision-table over constructed profiles — no GGUF parsing in the fit
tests, so the estimator is testable independently of the reader.

### 7.3 — `LlamaCppProvider`

Registered alongside Ollama. `REGISTRY` already takes two; `CatalogService`
already loops `self._runtimes`. This is where 05a's acceptance criterion —
"adding a fake llama.cpp runtime requires no change to llmfit parsing, curated
partitioning, or the frontend catalog schema" — becomes a real test.

Chat composes `OpenAICompatibleChatProvider` rather than reimplementing
streaming. Install fetches the GGUF into `--models-dir` with real filenames, not
llama.cpp's content-addressed HF cache layout (`LLAMA_CACHE` points at the app
data dir so nothing writes to `~/.cache`). Context set via `POST /models/load`
with `args`, on a ladder grown at turn boundaries.

**Tests:** a fake llama-server (aiohttp) covering health, models, props, load,
chat stream, delete; install against a fake HF serving a real small GGUF.

### 7.4 — Catalog: curated + search

Manifest `schema_version` 3: `artifacts.llamacpp = {repo, quant, mmproj}`, plus
`quality`, `estimated_tps`, `prefill_tps`, `ttft_ms`, `use_case`,
`capability_ids`, `license`, `decode_fraction` — all written by a CI job running
llmfit. Ships frozen; airgapped means no refresh path.

Search: `?filter=gguf&search=&sort=downloads&limit≤50`, 300 s TTL cache (HF
allows 500 requests per 5 minutes), `tree/main?recursive=true` for quants. Group
split parts (`-00001-of-00003`); exclude `mmproj*` and `*draft*` from the quant
list.

Gates: architecture in the 152-name list · chat template present · repo not
`gated` · disk space · physics. Nothing else.

Deleted: the collision-resolution block, `_placeholder_row()`,
`_synthetic_curated_model()`, `_runtime_target_model()`, the disk scan cache,
`CACHE_VERSION`, and the `scanned` flag through `AdvisorCatalog` →
`CatalogResult` → `RecommendationCatalogRead` → the frontend.

**Recommendation policy**, its own module and its own test file:

```text
fitting  = entries the estimator does not refuse
resident = fitting, weights entirely in VRAM
pleasant = resident, felt_cost(representative RAG turn) under floor

pleasant → max(quality, -size)        reason: best-quality-resident
                                       or speed-gated-quality if the floor
                                       eliminated a higher-quality candidate
resident → max(speed)                 reason: fastest-resident
else     → no recommendation; spilled entries stay installable
```

Quality is editorial and static per pinned file. Speed is physics per machine.
Predictions order candidates and gate the floor; they are never displayed.

> **RAG is prefill-dominated.** `HISTORY_BUDGET_TOKENS = 3000` plus ~24k
> characters of grounding is roughly 8,000 prefill tokens against ~300 decoded —
> the inverse of an agent's ratio. Decode is memory-bound; prefill is
> compute-bound, which is why CUDA leads Vulkan ~36–40% on `pp512` and ~10% on
> `tg128`. A decode-only prediction mis-ranks for this app. Use llmfit's
> `prefill_tps`/`ttft_ms` from the manifest until measured class constants exist.

**Tests:** policy decision-table across the six hardware profiles above.

### 7.5 — Packaging, three targets

`fetch-llamacpp.mjs`, pinned build number **and SHA-256** (`fetch-llmfit.mjs`
verifies a checksum; `fetch-ollama.mjs` does not — close that gap here, since
llama.cpp has no stable channel).

| Target | Asset | Size |
|---|---|---|
| darwin-arm64 | `bin-macos-arm64.tar.gz` | 11 MB |
| win32-x64 | `bin-win-vulkan-x64.zip` + `cuda-13.4` + `cudart` | 31 + 150 + 423 MB |
| linux-x64 | `bin-ubuntu-vulkan-x64.tar.gz` | 30 MB |

Verified: the Vulkan archive is the CPU archive plus exactly one file
(`libggml-vulkan.so` / `ggml-vulkan.dll`), and all CPU micro-architecture
variants ship inside — 15 on Windows, 10 on Linux. `ggml_backend_load_best()`
searches the executable's own directory and probes `cuda` before `vulkan`, so
the CUDA DLLs sit in the same flat folder and win automatically.

cudart carries `cudart64_*.dll`, `cublas64_*.dll`, `cublasLt64_*.dll`; all must
be beside `llama-server.exe` or it fails at launch with a missing-DLL error.

Prune to `llama-server` plus its libraries: 24 executables → 1, which also
shrinks the macOS notarization surface.

- **Linux:** `libggml-vulkan.so` has `DT_NEEDED: libvulkan.so.1`. deb adds
  `libvulkan1` to `Depends`; AppImage bundles the loader or accepts CPU (the ICD
  must come from the host driver). glibc floor is **2.34**.
- **Pin `ubuntu-22.04`.** `ubuntu-latest` migrates to 26.04 between 19 Oct and
  19 Nov 2026 and will silently raise the AppImage's glibc floor. The
  PyInstaller binaries already require 2.39 from the current runner, so this is
  a pre-existing portability bug that llama.cpp does not cause and this phase
  should fix.
- **macOS:** router mode spawns grandchildren under the hardened runtime.
- **Windows:** verify `taskkill /t /f` on the router PID reaps its model workers.

**Tests:** staged-checksum verification; per-OS smoke running `--list-devices`
from the final packaged resource path.

### 7.6 — Remove Ollama completely

~440 references across 66 files. The only irreversible phase.

**Delete:**

```text
backend/modules/llm/providers/ollama/          provider.py, catalog.py, __init__.py
backend/tests/unit/llm/recommendations/test_ollama_runtime.py
backend/tests/unit/llm/test_ollama_num_ctx.py
electron/src/main/sidecars/ollama.ts
electron/scripts/fetch-ollama.mjs
electron/ollama/                               501 MB staged
```

**Rewrite:** `shared/config.py` (`ollama_base_url`/`ollama_models_dir` →
`llamacpp_*`), `sidecars/types.ts` (`SidecarContext.ollama*`),
`sidecars/python.ts` (stops passing `OLLAMA_*`), `electron-builder.yml`,
`electron/package.json` (`build:ollama` and the `dist` chain),
`.github/workflows/release-local.yml`, `modules/llm/router.py`,
`modules/llm/resolution.py`, `modules/llm/selection.py`, `modules/chat/errors.py`.

**Frontend:** `selected-roles.tsx` (`llamacpp` → "Local"; a loopback connection
is arguably also "Local"), `chat-error-notice.tsx`. **Keep**
`connection-form.tsx`'s Ollama preset.

**Egress:** `ollama_pull → registry.ollama.ai` becomes two destinations against
`huggingface.co` — `model_download` (a repo you named) and `model_search` (text
you typed). Same host, different consent. `ollama_pull_host()`'s `hf.co/`
special-case disappears.

**Three things that will bite:**

1. **Do not touch revisions `0004` and `0009`.** They mention Ollama and are
   applied history on every installed machine. A new revision does the data work.
   `tests/integration/test_migrations.py` asserts historical schema — read it
   first.
2. **Existing users have a broken selection.** `SelectedModel(provider="ollama")`
   makes `resolve_generation()` raise `unknown provider` and chat dies. The
   migration clears it and the UI states why; the weights are in a blob format
   we no longer manage, so there is no silent remap.
3. **`<dataDir>/ollama/` is orphaned and gigabytes.** Offer to delete it. Leaving
   it silently is not acceptable in a local-first app.

**Definition of done:**

```bash
grep -rn -i ollama surfsense_local \
  --exclude-dir=node_modules --exclude-dir=release --exclude-dir=.venv
```

returns only the `connection-form.tsx` preset and its test, revisions `0004`
and `0009`, and the new migration's `WHERE destination = 'ollama_pull'`.

**Tests:** a migration test over a database seeded with an Ollama selection and
an `ollama_pull` egress row.

### 7.7 — Capabilities and multimodal

`Capabilities(inputs, tools, system_role, typed_content, context_tokens)` at the
`Generator` seam, from `GET /models.architecture.input_modalities` and
`GET /props.chat_template_caps` — template-derived truth, not a name regex.
`supports_system_role` matters immediately: `build_messages()` always emits a
system message and silently degrades on templates without it.

`Message.content` widens from `str` to `str | tuple[ContentPart, ...]`. The
adapter **downgrades at the seam**: a text-only model gets the image replaced by
its extracted text, never an error, so `modules/chat` never learns about
modality.

Retrieval stays text. Ingestion already writes page files; `image_url.url`
accepts a **local file path**, so the path Docling wrote is handed over directly
with no base64 round-trip. `--mmproj-auto` is on by default with `-hf`, so a
vision model brings its own projector.

> **ponytail:** [#19980](https://github.com/ggml-org/llama.cpp/issues/19980) —
> `--fit` does not account for mmproj VRAM, so vision models can OOM on tight
> machines. Add the projector bytes to our own sum.

Touches `Hit`, the chunk model, and citations. Ships after the swap, not with it.

### 7.8 — Constrained decoding and prompt consolidation

69 prompt files exist (23 cases × 3 tiers); **48 demand JSON**.
`response_format: {"type": "json_schema", "schema": {…}}` masks every token that
would produce invalid JSON, so malformed output becomes mechanically impossible.

Two caveats to design around now:

- The schema is **not** injected into the prompt. Fields still get described —
  once, not once per tier, because compliance no longer depends on persuasion.
- [#29006](https://github.com/ggml-org/llama.cpp/issues/29006): json_schema on
  the chat endpoint returns 400 for some templates while equivalent GBNF on
  `/completion` succeeds. Studio needs that fallback path.

`params_b` becomes exact from the GGUF header, retiring `_estimated_b()`'s
blob-size division and its `gemma3:4b` reads-as-5.5B `ponytail`.

Tiers do not disappear, but what they carry changes: after constrained decoding
and template caps, a tier carries **reasoning depth only**, not format
compliance. That plausibly collapses three tiers to two.

## Failure behavior

- Runtime missing or crashed: catalog stays visible, installs disabled, an
  already-selected remote connection still answers.
- No Vulkan loader: `dlopen` fails, backend skipped silently, CPU runs.
- HF unreachable: curated and installed render from the manifest and disk;
  search reports the destination is unavailable, not an error.
- Header read truncated: retry wider once, then fall back to a file-size estimate
  with the badge marked approximate.
- Physics refusal: state required and available bytes and name a smaller model.
- Cancelled download: `POST /models/unload`, partial file removed, never selected.

## Tests

- GGUF reader: truncated file, oversized vocab, split parts, Range retry.
- Estimator: decision-table over constructed profiles; f16 vs q8_0 KV (a 1 GB
  swing on an 8 GB machine, measured).
- Recommendation policy: the six hardware profiles above, asserting both pick
  and reason key.
- Catalog: curated renders with no network; search gated on egress; arch,
  template, and gated-repo rejections.
- Runtime: fake llama-server for health/models/props/load/chat/delete.
- Migration: an Ollama selection and an `ollama_pull` row, upgraded.
- Packaging: staged checksum; `--list-devices` from the packaged path per OS.

## Acceptance

- A clean machine on all three OSes opens the catalog with a hardware line and
  badged rows, with no scan button and no network.
- The recommended model installs and answers with citations.
- A model found through search — one Ollama's library never carried — installs
  and answers.
- A Windows machine with an RTX card runs on CUDA, from the installer alone.
- A machine with no usable GPU runs on CPU with no error.
- Airgapped: curated install from a local `.gguf`, chat, and Studio all work.
- `grep -i ollama` returns only the intended survivors.
- Quit leaves no orphan `surfsense-*` or `llama-server` process.

## Appendix — measurements

Taken on an M2 / 8 GB against llama.cpp `b11043` and llmfit `1.1.11`, except
where noted.

| Measurement | Value |
|---|---|
| GGUF repos on Hugging Face | 204,797 |
| llmfit embedded database | 11,271 models, 3,454 publishers |
| Ollama library | 240 models |
| llmfit rows with an `ollama_name` | 138 of 9,590 (1.4%) |
| llmfit rows resolvable under `--force-runtime llamacpp` | 1,109 of 6,804 fitting |
| llama.cpp supported architectures | 152 (`LLM_ARCH_*`) |
| `llmfit --json system` | 0.68 s |
| `llmfit --json fit` (full scan) | **0.84 s**, 9,590 rows, 17 MB JSON |
| `llmfit recommend -n 20000 --force-runtime llamacpp` | 0.72 s, 6,804 rows |
| `llama-server --list-devices` | 174 ms cold, 60 ms warm |
| `ggml_backend_dev_memory()` via ctypes | 180 ms warm, ~20 s first call on Metal |
| GGUF header over HTTP Range | 1.79 MB, 2.5 s (135M model) |
| macOS DMG today | 1,507 MB |
| `electron/ollama/` staged (macOS) | 501 MB — of which 380 MB is MLX, 66 MB the Go binary |

Hardware-dependence of llmfit fields, from two simulated machines
(`--memory 8G --ram 8G` versus `--memory 80G --ram 256G`, 3,047 models in common):

| Field | Changes with hardware |
|---|---|
| `parameter_count`, `params_b`, `context_length`, `license`, `use_case`, `capability_ids`, `runtime` | **no** — identical |
| `best_quant`, `memory_required_gb`, `estimated_tps`, `fit_level`, `score_components.quality` | yes |

Holding the quantization fixed (2,424 models): **quality differs 0/2424, memory
differs 0/2424.** Quality and memory are functions of *(model, quantization)*,
not of hardware — hardware only enters by choosing the quantization. That is
what makes a pinned manifest's numbers deterministic and build-time computable.

Device query versus advisor, same machine:

| | llmfit | `ggml_backend_dev_memory()` |
|---|---|---|
| Memory budgeted | 8.0 GB | **5,461 MiB** (Metal working set) |
| Context priced | 8,192 | 16,384 (our real turn) |
| Qwen3 8B verdict | **Perfect** | **uses system RAM** |

## References

- [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) — router mode, `/models`, `/models/sse`, `/props`
- [`ggml-backend-reg.cpp`](https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-backend-reg.cpp) — `ggml_backend_load_best()`, silent skip on `dlopen` failure
- [`common/jinja/caps.h`](https://github.com/ggml-org/llama.cpp/blob/master/common/jinja/caps.h) — `chat_template_caps` fields
- [PR #17485](https://github.com/ggml-org/llama.cpp/pull/17485) — automatic `n_gpu_layers`, graceful degradation
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) `hermes_cli/local_runtime/` — MIT; the closest shipped analogue. Four curated entries, one pinned variant each, `variants[-1]` unconditionally, headroom buys context not quantization.
