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
| **llmfit** | **Authoring-time only. Not shipped, and not in CI.** | A person runs `scripts/refresh_curated_models.py` when adding or changing a curated entry — a few times a year — and commits the numbers. llmfit is not a gate, not a hardware source, not in any request path, and not in the build. Removes 27 MB, a pinned version, and five failure modes per installer. |
| **Gating** | Only physics refuses | `can_install = state != TOO_BIG`, and `TOO_BIG` *is* the physics refusal — weights + KV at the 16K floor exceeding VRAM **plus** RAM. No other fit level gates anything; `PARTIAL` installs like `FITS`. Eligibility (architecture, chat template, gated repo) blocks separately and is not a fit state. See **Fit states**. |
| **Catalog** | Two tiers — curated manifest, and Hugging Face search | Curated is the offline product and ships frozen. Search is a network feature that is simply absent airgapped. |
| **Fit estimate** | Our own, from the GGUF header | llmfit cannot score a model outside its database (`llmfit plan` states the precondition). Search needs an estimate anyway; once it exists, llmfit's is redundant *and* less accurate here. |
| **`rank`** | **Curated entries only. A searched model never carries one, from llmfit or anywhere else** | A preference order over models we tested, **for this app's job** — answering from the user's documents with citations that resolve — not general capability. An integer typed by a person, with llmfit proposing. Called `rank`, not `quality`, because it is only ever a sort key: nothing reads its magnitude, so it must not imply a measurement we do not have. Attaching one to an arbitrary repo attaches a base model's score to a derivative that behaves differently: of the top 100 GGUF repos by downloads, 38 match an llmfit entry, and those matches include `Huihui-Qwen3.8-27B-abliterated-GGUF` and `Qwen3.8-27B-Uncensored-GGUF` resolving to the base model's score. A wrong number people trust is worse than a blank they investigate. Search rows are **described, not judged**. |
| **Search order** | `sort=downloads`, descending | The only HF sort that behaves as a default. Presented as a popularity fact, never as an endorsement. See **Search ordering**. |
| **Fit badge** | **Every row, both tiers** | Fit is subtraction, not judgement — the opposite of `rank`. Coarse from file size in the search list, exact from the header on open, exact from `shape` offline for curated. Three states, no `unknown`. |
| **Curated manifest** | **Stays, schema 3, authored by hand** | It is the whole product airgapped, the first-run default, and the only tier the recommendation reads. `scripts/refresh_curated_models.py` writes it; a person commits it; **llmfit never runs in CI**. |
| **Manifest validation** | Existing unit tests. **No new CI** | Pydantic (`extra="forbid"`, `model_validator`) plus `test_curated_models.py` already reject malformed manifests. A dead pin is a runtime failure, gracefully handled — CI cannot prevent a repo disappearing after the build anyway. `validated: true` is the real check, and it is a human one. |
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
         │          → FITS | PARTIAL | TOO_BIG   (TOO_BIG = the physics refusal)
         ▼
  CatalogService
     ├── curated   manifest: shape derived + rank by hand, ships frozen
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

**The two Qwen2.5-Coder entries are dropped.** SurfSense has no coding job — the
Studio formats are summary, flashcards, mindmap, quiz, podcast, office, web and
visuals, and chat is document Q&A with citations. A coding model was taking two
of eight slots in a list whose real gaps are a rung for 48-64 GB machines and a
vision entry. Anyone who wants one searches for it, gets a fit badge, and
installs it — that is what the search tier is for.

The shipped six, measured at Q4_K_M and a 16K window:

| model | file GB | layers | kv_heads | needs @16K |
|---|---|---|---|---|
| Qwen3 0.6B | 0.40 | 28 | 8 | 2,354 MiB |
| Qwen3 1.7B | 1.11 | 28 | 8 | 3,032 |
| Qwen3 4B | 2.50 | 36 | 8 | 4,630 |
| Qwen3 8B | 5.03 | 36 | 8 | 7,043 |
| Qwen3 14B | 9.00 | 40 | 8 | 10,969 |
| Qwen3 32B | 19.76 | 64 | 8 | 22,047 |

What each machine gets:

```text
machine          0.6B 1.7B   4B   8B  14B  32B   →  recommended
M2 8 GB           GPU  GPU  GPU  RAM  RAM    —   →  Qwen3 4B     (831 MiB spare)
RTX 3050 6 GB     GPU  GPU  GPU  RAM  RAM  RAM   →  Qwen3 4B     (490 MiB spare)
M4 16 GB          GPU  GPU  GPU  GPU  RAM  RAM   →  Qwen3 8B   (3,857 MiB spare)
RTX 4070 12 GB    GPU  GPU  GPU  GPU  GPU  RAM   →  Qwen3 14B     (31 MiB spare)
RTX 4090 24 GB    GPU  GPU  GPU  GPU  GPU  GPU   →  Qwen3 32B    (953 MiB spare)
M4 Max 64 GB      GPU  GPU  GPU  GPU  GPU  GPU   →  Qwen3 32B  (26,000 MiB spare)
```

Every machine gets a GPU-resident pick, so six rungs strand nobody. Three gaps:

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
3. **A vision entry.** All six are text-only, in an app with a PDF pipeline.
   Vision is a **capability**, not a separate list — see **Ranking**.
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

**`curated-models.json` stays.** It is the only tier that works with no network,
so it is the entire product airgapped, the default on first run, and the only
thing the recommendation can read. It ships frozen in the build; there is no
refresh path.

Manifest `schema_version` **3**. One entry, before and after:

```jsonc
// v2 — today
{
  "model_id": "Qwen/Qwen3-8B",
  "family": "Qwen3",
  "minimum_fit": "good",
  "minimum_context": 8192,
  "allowed_quantizations": ["Q4_K_M"],
  "artifacts": { "ollama": { "name": "qwen3:8b", "quantization": "Q4_K_M" } },
  "label": "Qwen3 8B",
  "parameter_count": "8B",
  "size_bytes": 5225374496
}

// v3
{
  "model_id": "Qwen/Qwen3-8B",
  "family": "Qwen3",
  "label": "Qwen3 8B",
  "parameter_count": "8B",

  // ── DERIVED. The script writes all of this. No human input, ever. ──
  "artifacts": {
    "llamacpp": {
      "repo": "unsloth/Qwen3-8B-GGUF",
      "file": "Qwen3-8B-Q4_K_M.gguf",
      "quantization": "Q4_K_M",
      "size_bytes": 5027784512,
      "mmproj": null
    }
  },
  // Estimator inputs, read from the real GGUF header at authoring time.
  "shape": {
    "architecture": "qwen3",
    "block_count": 36,
    "head_count_kv": 8,
    "key_length": 128,
    "value_length": 128,
    "context_length": 40960,
    "n_vocab": 151936
  },
  "capabilities": [],           // user-facing only. Today: "vision" or nothing.

  // ── JUDGEMENT. Two fields, typed by a person. ──
  "rank": 83,               // our preference order for document Q&A.
                            // Not a benchmark. Never displayed.
  "validated": true,        // someone downloaded this exact file and ran it

  "decode_fraction": 1.0    // 1.0 dense; the active slice for MoE (not derivable
}                           // from the header — set by hand, see below)
```

**The split is the point.** Everything above the line comes free from the GGUF
header and the Hugging Face listing; everything below it is three small decisions
a person makes in a minute. That is what keeps the manifest maintainable at
twenty entries instead of six — the tedious half scales automatically, the half
that needs a brain stays tiny.

**`shape` is what makes the curated tier work offline.** Pricing a model means
reading its GGUF header, and a curated entry is not downloaded yet — so without
these fields an airgapped machine has no fit badge on the one tier it can use.
Committing what the header said at authoring time is what lets `weights +
KV(16K) + overhead` run against the manifest alone, on first paint, with no
network. It is the same reason Hermes carries estimator inputs inline.

`decode_fraction` is the fraction of the build's bytes read per decoded token —
`1.0` dense, the active slice for MoE. Without it an MoE entry's speed
prediction is wrong by an order of magnitude, which matters the moment the
80B-A3B-class rung lands.

`validated: true` means a person downloaded that exact file and ran it. False is
allowed and honest; it is not a gate.

Dropped from v2: `minimum_fit` (a gate — only physics gates now),
`allowed_quantizations` (redundant once `artifacts.llamacpp` names the file),
`minimum_context` (the context ladder and the model's own `context_length`
replace it), and top-level `advisor_providers` (scoped an llmfit scan that no
longer runs).

#### Authoring

A script run by hand, **never CI**. The manifest is **source, not build output**.

```bash
$ uv run scripts/refresh_curated_models.py \
    --add Qwen/Qwen3-Next-80B-A3B \
    --repo unsloth/Qwen3-Next-80B-A3B-GGUF --quant Q4_K_M

  resolving unsloth/Qwen3-Next-80B-A3B-GGUF … Q4_K_M found, 45.2 GB
  reading GGUF header (4 MB range) … qwen3next, 48 layers, 2 kv-heads, ctx 262144
  llmfit … best_quant=Q4_K_M ✓ matches pin
  llmfit proposes rank 94  (would be highest in the list — currently 92)

  ⚠ MoE detected — decode_fraction not derivable from the header. Set it manually.
  ⚠ validated=false until you run this file.

  wrote curated-models.json (+1 entry)
```

The person then downloads it, chats with it, confirms citations resolve, sets
`decode_fraction` and `validated: true`, and commits. Twenty minutes, most of it
waiting for the download.

```text
every build
    read the committed JSON. No llmfit, no network, no subprocess.
```

**What triggers a refresh** — events, not a schedule; realistically four or five
a year:

| Trigger | Cadence |
|---|---|
| A model worth recommending ships (a new family, a good MoE, a vision entry) | the main one |
| A quantizer deletes or re-uploads a pinned file, so users hit a 404 | reactive |
| The pinned llama.cpp build is bumped and pins want re-verifying | on bump |
| A hardware class is under-served (see **The quantization ladder**) | occasional |
| Someone reports a bad recommendation | reactive |

**The budget flags are mandatory.** Run bare, llmfit detects whatever laptop the
script is on and grades a quantization nobody pinned, so the numbers would
describe a different file than the one in `artifacts`. The `best_quant`
assertion catches that at authoring time, where a person is already looking.

> **ponytail:** llmfit has no way to request a score at a named quantization —
> `plan --quant` returns memory requirements but carries no quality field. Until
> it does, the declared budget is chosen so llmfit lands on the pinned quant, and
> the assertion above is what keeps the two in step.

Numbers are source rather than build output for three reasons beyond speed: a
rank moving 78 → 94 appears in a pull request where someone notices, a tag
rebuilds to the same manifest forever, and the cadence is honest — these change
when someone adds a model, not when someone cuts a release.

#### Ranking

`rank` orders the curated rows and selects the ★. It does **two** things and
nothing else. It is never displayed, never compared outside the app,
and never applied to a searched model.

Because it is only ever a sort key, it does not need to be a measurement — it
needs to be an **order**. Hence `rank`, not `quality`: calling it quality would
imply we measured something we did not.

**`rank` means "good at this app's job"** — answering from the user's documents
with citations that resolve — not general capability. That distinction does real
work. llmfit rates Qwen2.5-Coder 7B at **89** against Qwen3 8B's **83**, because
it is measuring coding ability; for document Q&A the coder is the weaker model
and should rank *below* it. A proposal that grades the wrong task is exactly what
the human review step exists to correct.

**llmfit proposes; a person decides.** It carries real model-specific signal —
grouping ~4,000 scored models by *(parameter count, quantization)*, 224 of 230
groups show quality varying between models of identical size and quant, so it is
not parameter count in disguise. But it is unreliable on models it does not know
well:

```
22.1B @ Q6_K
   100.0   mconcat/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-NV
   100.0   crushleorey/Qwopus3.6-27B-v2-NVFP4
    88.0   upstage/solar-pro-preview-instruct
```

Community fine-tunes scoring a perfect 100, above published models. That number
is closer to the name than to measured behaviour. It behaves on models it knows
properly — the shipped six come back `38 · 53 · 68 · 83 · 90 · 92`, monotonic
and sanely spread — which is exactly the population the curated tier draws from.

Three checks before committing a rank:

1. within a family, rank rises with parameter count — the invariant in **Tests**
2. anything at or near 100 is suspect; nothing worth curating maxes a scale
3. crossing families, cross-check a public leaderboard — that is the comparison
   llmfit is least reliable at
4. a specialist (a coder, a reasoning-tuned variant) is ranked for *this* task,
   not for the task it was tuned on

If llmfit has no entry, or proposes something absurd, **type the integer by
hand**. The field is an int; nothing requires llmfit to have produced it. A
number written by someone who ran the model beats a scraped 100.

**Parameter count is not a sufficient substitute.** Within the shipped six it
happens to work, since they are one family of dense models. It breaks the moment
the list grows: MoE (80B total, ~3B active reads nothing like a dense 80B),
a second dense family where sizes stop being comparable, and any specialist whose
size says nothing about how it handles documents.

**One list, not tracks.** SurfSense has one job — the Studio formats are summary,
flashcards, mindmap, quiz, podcast, office, web and visuals, and chat is document
Q&A. All twenty-three prompt cases are the same shape: read documents, write
prose or JSON. A single ranking is therefore meaningful, and splitting it would
import a general-catalog framing this app does not need.

**Vision is a capability, not a rank position.** Nobody chooses a vision model
*instead of* a general one; they need one when the documents are images. It is
already in the manifest, derived from the header and `input_modalities` (and
gated on `typed_content` — see **7.7**):

```jsonc
"capabilities": ["vision"]
```

So the ★ stays "the best-ranked model that fits", and a vision entry surfaces
when it is relevant (*your PDFs contain scanned pages, and this model can read
them*), never as a competitor in the ordering. `vision` is the only capability
that reaches the UI; everything else `chat_template_caps` reports is an internal
constraint.

Tracks would only be warranted if SurfSense gained jobs wanting genuinely
different models — a conversational model for podcasts against an analytical one
for chat, say. Nothing today does.

**If llmfit disappears tomorrow:** committed ranks are unaffected, the schema is
unaffected (`rank` is an int), the refresh script loses its proposer and a person
types the number, and the app never knew about it. That is the test a long-term
dependency should pass, and the reason to keep it outside the product.

> **Long-term destination, not phase 7.** llmfit grades general capability.
> SurfSense needs something narrower: *does this model answer from the user's
> documents, and cite the right chunks?* No external leaderboard measures that.
> The honest end state is a small internal eval — 20-40 fixed questions over a
> fixed document set, run through the real chat path, scored on whether the
> answer came from the sources and whether `[n]` citations resolved — with `rank`
> set from that. It measures the actual pipeline, catches the RAG failure that
> matters most (answering confidently *without* the sources), reruns in minutes,
> and would also tell you whether the compact/capable/frontier tier split still
> earns its keep after 7.8 lands. Nothing measures that today.

**Staleness is acceptable, by design.** Airgapped means no refresh path, so a
shipped list ages. That would be fatal if curated were the only way to get a
model. It is not: 204,797 models are one search away, badged and installable,
with no rank attached. So curated ages into "a starting point we tested a while
ago" rather than a boundary — which is what makes a few-times-a-year cadence a
choice instead of a liability.

**Search:** `?filter=gguf&search=&sort=downloads&direction=-1&limit≤50`, 300 s
TTL cache (HF allows 500 requests per 5 minutes), `tree/main?recursive=true` for
quants. Group split parts (`-00001-of-00003`); exclude `mmproj*` and `*draft*`
from the quant list.

Gates: architecture in the 152-name list · chat template present · repo not
`gated` · disk space · physics. Nothing else.

**Gate on the header, not on Hugging Face's tags.** Counted on `library=gguf`:

| `pipeline_tag` | GGUF repos |
|---|---|
| `text-generation` | 37,849 |
| `image-text-to-text` | 5,327 |
| `any-to-any` | 315 |
| `audio-text-to-text` | 27 |
| `automatic-speech-recognition` | 547 — not chat |
| `feature-extraction` | 681 — embeddings, exclude |

That totals ~43,500 of 204,797, so **roughly 80% of GGUF repos carry no useful
pipeline tag at all** — filtering the search by tag would hide four-fifths of the
catalog, including working chat models whose uploader left the field blank. The
two header gates do the job structurally instead: a supported architecture
excludes Whisper-type models, and a present chat template excludes embedding
models. Pipeline tags are worth offering as an optional facet ("vision models
only"); they are not the gate.

**Search ordering.** All five HF sort fields work on `filter=gguf`; only one is
usable as a default:

| `sort=` | Top result | Verdict |
|---|---|---|
| `downloads` | `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` | **default** |
| `likes` | `unsloth/Qwen3.8-27B-GGUF` | surfaces uncensored derivatives in the top few |
| `trendingScore` | `prism-ml/Ternary-Bonsai-2-27B-gguf` | same |
| `lastModified` | `tapiocaTakeshi/Qubit` | surfaces half-finished uploads |
| `createdAt` | `mradermacher/HuatuoGPT-3-9B-i1-GGUF` | same |

Every order surfaces abliterated and uncensored fine-tunes somewhere near the
top. That is what an open catalog means, and it is not a reason to reintroduce
grading — the curated tier is what serves someone who does not want to evaluate
models, and it is the only tier the recommendation reads. Copy must present the
count as popularity, not endorsement.

**What a search row shows** — facts about the file, never a judgement of it:
fit verdict · size per quantization · architecture · context length · chat
template present · vision capability · license · gated · downloads, likes,
last updated · **provenance**.

Provenance is free and worth surfacing: 32 of the top 40 GGUF repos carry a
`base_model:quantized:<repo>` tag, so a row can read *"quantized from
`Qwen/Qwen3.8-27B`"*. That is a statement about where the file came from, not a
grade — and it is most of what a quality score was doing for a user anyway,
letting them recognise an unfamiliar repo as a repackaging of a model they know.
The 8 of 40 with no such tag are informative by their absence.

**Fit badges appear on both tiers. Quality appears on neither.** These look
alike and are not:

| | What it is | Needs | Where |
|---|---|---|---|
| fit badge | subtraction — does this file fit in this memory | device memory + file size | **every row, both tiers** |
| `rank` | a preference order over models we tested | a person to have decided | curated only, and never displayed |

"This 40 GB file will not fit in your 8 GB of memory" is no more a judgement than
"this file is 40 GB", and it is the single most useful thing to tell someone
browsing 204,797 models they have no size intuition for. Withholding it does not
protect them; it makes them download 40 GB to find out.

Two stages, so the list stays cheap:

```text
search list   file size is already in the HF response
              → coarse badge from size alone, no extra request

open a model  read 2-4 MB of its GGUF header (2.5 s)
              → exact badge, conversation memory included

curated       shape is in the manifest
              → exact badge offline, on first paint
```

#### Fit states

Badge vocabulary changes meaning with the swap. It stops being llmfit's
five-level score (`perfect`/`good`/`marginal`/`too_tight`/`unknown`) and becomes
a three-state statement about **where the weights will live**. There is no
`unknown`: every row has a file size, so every row has a badge.

Let `need = weights + KV(window) + overhead`, `vram` = usable device memory from
the budget probe, `ram` = host memory available to the budget.

| State | Condition | What happens at load |
|---|---|---|
| `FITS` | `need ≤ vram` | every layer on the device, full speed |
| `PARTIAL` | `vram < need ≤ vram + ram` | `--fit` places some layers on the CPU; runs, slower |
| `TOO_BIG` | `need > vram + ram` at the **16K floor** | physics refusal — the only state that blocks install |

`TOO_BIG` is evaluated at the floor, not at the requested window: a model that
will not fit at 16K cannot be rescued by a smaller context, and the remedy to
offer is a smaller quantization or a smaller model.

**Wording is per platform. The state set is not.** One label set is wrong on two
of the three targets, so the copy branches on two facts the budget already
carries: `uma`, and whether any non-CPU device exists.

A badge is a **verdict plus one plain line of why**. The verdict is what someone
choosing a model needs (fast, slower, or impossible); the mechanism is the
explanation, not the headline.

**Discrete GPU** (Windows or Linux with an NVIDIA or AMD card)

```text
●  Full speed        Runs entirely on your graphics card
◐  Reduced speed     Too big for your graphics card, so part runs on the processor
○  Won't fit         Needs about 21 GB. This PC has 13.6 GB
```

**Apple Silicon** (`uma`)

```text
●  Full speed        Runs entirely on the GPU
◐  Reduced speed     Too big for the GPU, so part runs on the CPU
○  Won't fit         Needs about 21 GB. This Mac has 13.6 GB
```

**No GPU device** (`--list-devices` prints `(none)`)

```text
●  Works here        Runs on your processor
○  Won't fit         Needs about 21 GB. This PC has 16 GB
```

Terse variant, if rows are tight: verdict as the badge, reason as dimmed
trailing text, full explanation in the row's detail view.

```text
●  Full speed
◐  Reduced speed     (part runs on the processor)
○  Won't fit         (needs 21 GB, you have 13.6 GB)
```

**"Full speed", not "Fast".** Fast is a promise the badge cannot keep: a 32B
running entirely on a 4090 is still slower than a 4B. *Full speed* is relative
to the model, which is exactly what the state means — as fast as this machine
can run this particular model. Same reason *Reduced speed* beats *Slower*: it
says reduced from what it could be, not slow in absolute terms.

**"Works here" on a machine with no GPU.** Technically that case is `FITS`, but
"Full speed" reads as a boast about a slow situation when there is no faster
alternative to contrast with. The useful information is simply: yes, you can run
this. That is the one place the verdict word differs and not just the
explanation.

On Apple Silicon there is no separate system RAM to spill into. A model over
Metal's working set is not copied anywhere; llama.cpp runs some layers on the CPU
backend against the same physical memory, so "uses system RAM" would describe a
transfer that does not happen. With no GPU at all, `FITS` means the processor and
`PARTIAL` is unreachable because there is nothing to spill from.

> **Copy rule for every user-facing string in this phase: no em dashes and no
> hyphens.** Use commas, full stops or parentheses. Applies to badges, empty
> states, error copy and the recommendation line.

> **Optional refinement, not a design change.** `PARTIAL` spans a wide range: 5%
> spilled is barely noticeable, 70% crawls. The number is already known
> (`need - vram`), so the reason line can be graded without adding a state —
> *"A little too big for the GPU. Most of it still fits."* against *"Well over
> your GPU's memory. Expect it to be slow."* Same badge, sharper sentence. Ships
> after the first version if wanted.

> **Decision: `PARTIAL` stays available on unified memory.** Hermes'
> `_uma_budget()` sets `ram_available_bytes = 0`, so on Apple Silicon their
> physics check is `need ≤ vram` alone and the middle state cannot occur — on an
> 8 GB M2 that refuses Qwen3 8B (7,043 MiB against ~5,461) outright. We do not
> copy that. It genuinely runs with CPU layers, and refusing it removes a real
> option from the users with the least choice. On UMA the refusal threshold is
> total RAM, not the device working set.

**One modifier, not a fourth state.** A search row badged from file size alone,
and a row whose header read was truncated, carry the same three states at lower
precision — rendered as approximate (a `~`, or a lighter treatment) and resolving
to the firm badge once the header lands.

**Eligibility is not fit.** These block or warn independently and must not be
rendered as fit states — a model can be `FITS` and still gated:

| Condition | Effect |
|---|---|
| architecture not in llama.cpp's 152-name list | not installable; no amount of memory helps |
| no chat template in the header | installable, warns — will produce garbage in a chat UI |
| repo is `gated` | needs a Hugging Face account before the download resolves |

#### List order

Curated sorts by `(fit state, -rank, model_id)` — fit coarsely, rank finely —
which is what today's `_sort_key` already does. Sorting by rank alone would put a
`TOO_BIG` 32B at the top of an 8 GB machine's screen.

The recommendation is the top row of the `FITS` bucket, subject to the speed
floor. Search sorts by downloads.
**Neither list displays a rank**; rank only orders curated rows and selects the
recommendation.

**A searched model can be installed, selected, and used. It can never be
recommended**, because recommending requires ranking and ranking requires a
`rank` that only the manifest carries. The two tiers differ in kind, not degree.

Deleted: the collision-resolution block, `_placeholder_row()`,
`_synthetic_curated_model()`, `_runtime_target_model()`, the disk scan cache,
`CACHE_VERSION`, and the `scanned` flag through `AdvisorCatalog` →
`CatalogResult` → `RecommendationCatalogRead` → the frontend.

**Recommendation policy**, its own module and its own test file:

```text
fitting  = entries the estimator does not refuse
resident = fitting, weights entirely in VRAM
pleasant = resident, felt_cost(representative RAG turn) under floor

pleasant → max(rank, -size)           reason: best-rank-resident
                                       or speed-gated-rank if the floor
                                       eliminated a higher-ranked candidate
resident → max(speed)                 reason: fastest-resident
else     → no recommendation; spilled entries stay installable
```

Rank is editorial and static per pinned file. Speed is physics per machine.
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

**Two kinds, two sources, and only one of them reaches the UI.**

```text
GET /models → architecture.input_modalities     what the model can ACCEPT
GET /props  → chat_template_caps                what the TEMPLATE supports
```

| | Field | Surfaced? |
|---|---|---|
| **Capability** | `vision` | **yes** — a row badge and a search facet |
| **Constraint** | `supports_system_role` | no — changes how the request is built |
| **Constraint** | `supports_typed_content` | no — precondition for vision |
| Recorded, unused | `tools`, `tool_calls` | no |
| Recorded, unused | reasoning support | no |

One struct is fine; one *list that reaches the renderer* is not.
`supports_system_role` is meaningless to a person and `typed_content` is an
implementation detail. The manifest's `capabilities` array carries only the
user-facing set, which today means `["vision"]` and nothing else.

**`supports_system_role` matters immediately.** `build_messages()` always emits a
system message and silently degrades on templates that do not support one. That
is a live bug the swap fixes.

**Vision needs both halves.** "The model accepts images" is the obvious check and
it is not sufficient:

```python
can_see = Modality.IMAGE in caps.inputs and caps.typed_content
```

A model can accept images architecturally while its chat template takes only
string content, leaving no way to hand it one. Checking `input_modalities` alone
produces a vision badge on a model that cannot be sent a picture.

**What is deliberately absent.** `audio` and `video` are not modelled, because
nothing can feed them: Docling's `allowed_formats` in `worker/ingestion/parsing.py`
is PDF, DOCX, PPTX, XLSX, HTML, CSV, MD and **IMAGE**. Podcasts are audio *out*
and Kokoro owns that; audio *in* would need ingestion to accept and transcribe
media first, at which point `audio` becomes relevant and not before. `tts` and
`embedding` are fixed (Kokoro, and bge-small against a 384-dimensional index).

`IMAGE` being in that list already is what makes vision worth doing at all:
SurfSense accepts standalone images today, on top of PDF pages that are
effectively pictures. A vision model has something to look at on day one.

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
- `TOO_BIG` (the physics refusal): state required and available bytes and name a
  smaller quantization or a smaller model. Never a bare disabled control.
- Cancelled download: `POST /models/unload`, partial file removed, never selected.
- **Dead curated pin** (the repo or file 404s at download): say the model is no
  longer available from this source, drop it from the recommendation, and fall
  through to the next-best entry. This must be handled here rather than checked
  at build time — a repo can disappear between the release and a user's first
  install, so no pre-flight check can prevent it.

## Tests

- GGUF reader: truncated file, oversized vocab, split parts, Range retry.
- Estimator: decision-table over constructed profiles; f16 vs q8_0 KV (a 1 GB
  swing on an 8 GB machine, measured).
- Fit states: each of `FITS` / `PARTIAL` / `TOO_BIG` at its boundary, ±1 byte;
  `TOO_BIG` evaluated at the 16K floor, not the requested window; `PARTIAL`
  reachable on a `uma` budget (the Hermes divergence — a regression here silently
  refuses Qwen3 8B on an 8 GB Mac); `PARTIAL` unreachable with no GPU device;
  `can_install` true for `PARTIAL` and false only for `TOO_BIG`; copy resolves to
  the right platform wording for all three budget shapes.
- Recommendation policy: the six hardware profiles above, asserting both pick
  and reason key; and that a searched row is never eligible to be the pick.
- Catalog: curated renders with no network; search gated on egress; arch,
  template, and gated-repo rejections; a search row carries no `rank` field at
  all — asserted on the serialized response, so it cannot be reintroduced
  silently.
- Manifest (extends `test_curated_models.py`, which already covers unique ids,
  display metadata, and each rejection path): every entry has a `shape`, a
  `rank` and a pinned `quantization`; every `shape.architecture` is
  in the 152-name list; a curated row prices and badges with no network at all.
- **`rank` rises with parameter count within a family.** Today this passes
  trivially — the shipped six are one family and score `38 · 53 · 68 · 83 · 90 ·
  92`. The first failure is the signal to look, and it is expected: a
  mixture-of-experts, a second dense family, or a specialist ranked for document
  Q&A rather than for what it was tuned on will all break size-ordering
  legitimately. The assertion exists to make that a decision, not a drift.
- A curated entry with a `vision` capability is never preferred over a
  higher-ranked text model for the ★; capabilities do not enter the ordering.
- Capabilities: `vision` requires **both** `IMAGE in inputs` and
  `typed_content`; a model with image input and a string-only template reports
  no vision badge. `supports_system_role` false routes the system message into
  the first user turn rather than dropping it. Only the user-facing set reaches
  the serialized response — `system_role` and `typed_content` never appear in
  an API payload.
- Runtime: fake llama-server for health/models/props/load/chat/delete.
- Migration: an Ollama selection and an `ollama_pull` row, upgraded.
- Packaging: staged checksum; `--list-devices` from the packaged path per OS.

No new CI job. The build stays install → freeze → package → sign; neither llmfit
nor `huggingface.co` appears in it.

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
