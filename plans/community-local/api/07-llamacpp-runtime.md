# API — Phase 7: Replace Ollama with llama.cpp

> Owns: `modules/llm/providers/`, the runtime sidecar, the model catalog, and
> packaging for all three targets. Supersedes the Ollama runtime decision in
> [`../00-umbrella-plan.md`](../00-umbrella-plan.md) and the `hf.co/` fallback in
> [`05d-llmfit-catalog-expansion.md`](05d-llmfit-catalog-expansion.md). Extends
> [`05a-model-recommendations.md`](05a-model-recommendations.md), which is
> reduced to what survives here: prompt tiers, fingerprinting and onboarding.

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
| **Recommendation** | Highest `rank` among `FITS` entries. **No speed gate in v1** | A latency gate needs a prefill model, and llmfit's `prefill_tps` is an estimate for a generic machine. Rather than invent a threshold, v1 starves the gate: the ★ is the best-ranked entry that fits entirely on the device, tie-broken toward the smaller build. Additive once `llama-bench pp512` numbers exist per device class. |
| **Curated manifest** | **Stays, schema 3, authored by hand** | It is the whole product airgapped, the first-run default, and the only tier the recommendation reads. `scripts/refresh_curated_models.py` writes it; a person commits it; **llmfit never runs in CI**. |
| **Why `rank` can be authored at all** | Quality is a function of *(model, quantization)*, not of hardware | Measured twice: across 2,424 models at a fixed quant, quality differs 0/2424; and on one model swept 12G to 48G, quality does not move once `best_quant` stops moving. Hardware reaches quality through exactly one channel, the quantization, and pinning the file closes it. So the number is a property of a file, computable once and shipped as data, and a scan on the user's machine has nothing to discover. This is the load-bearing fact under the whole authoring design. See **Appendix**. |
| **Which llmfit field** | `score_components.quality` only. **`score` is discarded** | `score` blends fit, speed and context into quality, so three of its four terms describe a machine. In the same sweep it runs 65.1, 63.8, 63.6, 66.2, 63.6, 67.4 — non-monotonic and hardware-dependent. The composite is a statement about a laptop; the component is a statement about a file. Same reason `fit_level`, `memory_required_gb`, `estimated_tps` and `best_quant` are all read and thrown away. |
| **Scoring quantization** | The pinned one, found by a ladder sweep. A miss is a hard failure | llmfit cannot be asked for a score at a named quantization, and quality tracks `best_quant` exactly, so the budget decides which file gets graded. Qwen3 8B is **78** at the pinned Q4_K_M and **83** at Q8_0. See **Scoring at the pinned quantization**. |
| **Manifest validation** | Existing unit tests. **No new CI** | Pydantic (`extra="forbid"`, `model_validator`) plus `test_curated_models.py` already reject malformed manifests. A dead pin is a runtime failure, gracefully handled — CI cannot prevent a repo disappearing after the build anyway. `validated: true` is the real check, and it is a human one. |
| **Hardware budget** | `ggml_backend_dev_memory()` via `ctypes`, from the shipped libs | The allocator's own view. Falls back to `llama-server --list-devices`, then OS APIs. |
| **Downloads** | **SurfSense fetches the GGUF**, not `POST /models` | `llama-server` is a second process we do not proxy; an in-process fetch is the only place `egress.require()` actually holds. Also buys resume, checksums, and the header as the file lands. |
| **Quantization** | **One pinned file per entry in v1** | A pinned file is what "tested by SurfSense" can honestly claim. Per-machine selection is possible at no extra cost (one header read prices every quant), so a second variant on the largest entries is a cheap follow-on, not v1. See **The quantization ladder**. |
| **Context** | **Fixed at load. Floor 16K, capped at the model's own `context_length`** | llama.cpp fixes context at load, so `num_ctx()`'s per-request sizing has no equivalent. The floor is 3K history plus ~8K grounding plus a reply. Growing on occupancy is additive later; it needs a mid-conversation reload and two constants with nothing measured behind them. |
| **GPU backend** | **Vulkan on every platform off Apple Silicon. No CUDA** | Measured on an RTX 3050 at `b11050`: CUDA leads Vulkan **9.1%** on `pp512`, **10.2%** on `pp8192`, **2.1%** on decode — 0.66 s on an 11 s turn, for 685 MB. Vulkan covers NVIDIA, AMD and Intel from one 31 MB archive, its loader ships with Windows, and it is what the app already does today (`pruneCudaRunners()`). CUDA is specified as an optional later addition in [`08-cuda-backend.md`](08-cuda-backend.md), which needs **no code change** — ggml selects it by the files present. |
| **Device selection** | First device with `type == GPU`. **Never sum** | The same physical card appears once per loaded backend, and an integrated GPU can advertise more memory than a discrete one (16198 MiB against 6002 MiB, measured). ggml's ordering already expresses backend preference, so this **is** backend selection. Specified in **7.2**. |
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
  1,024 MiB overhead; at Hermes' 2 GiB margin floor it does not fit and that
  machine drops a rung.

**Manifest growth is follow-on work, not phase 7.** v1 ships these six re-pinned
to GGUF; the runtime swap is the deliverable and the search tier covers the gaps
meanwhile. In priority order, once it lands:

1. **A rung above 32B** — an 80B-A3B-class MoE. The only thing that serves
   48–64 GB machines. An MoE is the right shape for them: 80B of memory but ~3B
   read per token, so it is the only way to spend that memory without the machine
   crawling. Needs the `decode_fraction` field, which is computed from the header
   (see **Authoring**) — without it the speed prediction is wrong by roughly 10×.
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

## Contracts

> **Provenance.** The shapes and runtime calls below are grounded: the
> llama-server README at `b11043`, `nm` on the shipped libraries plus a live
> `ctypes` call, real GGUF headers read over HTTP Range, and live Hugging Face
> responses. **The HTTP routes are proposed, not reported** — no such surface
> exists yet. They follow this codebase's conventions: the `/llm` prefix, `*Read`
> Pydantic response models in `modules/llm/schemas.py`, and the NDJSON
> `{"type": …}` stream frame that `_event()` already emits.

### Domain shapes

```python
@dataclass(frozen=True)
class GgufArtifact:
    """One downloadable build. `file` is required: a repo holds ~20 quants, and
    repo + quantization does not name one (Q4_K_M vs UD-Q4_K_M vs a split set)."""
    repo: str                 # "unsloth/Qwen3-8B-GGUF"
    file: str                 # "Qwen3-8B-Q4_K_M.gguf"
    quantization: str         # "Q4_K_M"
    size_bytes: int
    mmproj: str | None = None # vision projector, fetched alongside
    # A curated manifest variant is this plus judgement (`rank`, `rank_basis`,
    # `validated`); a searched build is this alone. The runtime never sees the
    # judgement half — see 7.4.


@dataclass(frozen=True)
class ModelShape:
    """Estimator inputs. Committed to the manifest for curated entries, read from
    the header for everything else. Names mirror the GGUF metadata keys."""
    architecture: str         # general.architecture
    block_count: int          # <arch>.block_count
    head_count_kv: int        # <arch>.attention.head_count_kv
    key_length: int           # <arch>.attention.key_length
    value_length: int         # <arch>.attention.value_length
    context_length: int       # <arch>.context_length
    n_vocab: int
    sliding_window: int = 0   # <arch>.attention.sliding_window
    expert_count: int = 0     # <arch>.expert_count; > 0 means MoE


@dataclass(frozen=True)
class HardwareBudget:
    usable_vram_bytes: int    # capacity (total − margin) or live (free now)
    total_device_bytes: int
    ram_available_bytes: int
    uma: bool                 # unified memory: selects badge copy and headroom
    has_gpu: bool             # False when --list-devices prints "(none)"


class FitState(StrEnum):
    FITS = "fits"
    PARTIAL = "partial"
    TOO_BIG = "too_big"


@dataclass(frozen=True)
class FitVerdict:
    state: FitState
    need_bytes: int           # weights + KV(window) + overhead
    budget_bytes: int         # vram, or vram + ram for the TOO_BIG comparison
    approximate: bool = False # priced from file size alone, header not read yet


@dataclass(frozen=True)
class ContentPart:
    kind: Literal["text", "image"]
    text: str | None = None
    path: str | None = None   # local file path; image_url.url accepts one
```

`Capabilities` is defined in **7.7**. `Message.content` widens to
`str | tuple[ContentPart, ...]` there and nowhere else.

### HTTP routes — proposed

**Two catalog endpoints, deliberately.** Curated plus installed renders offline
and instantly; search needs `huggingface.co` and is paged. One response covering
both would either block on the network or return partial results behind a flag,
which is the `scanned` flag this phase deletes.

| Route | Returns | Network |
|---|---|---|
| `GET /llm/system` | `HardwareBudget` plus device list | none |
| `GET /llm/catalog` | `{curated: [...], installed: [...]}`, every row badged | **none** |
| `GET /llm/search?q=&limit=&cursor=` | HF hits, coarse badge from file size | huggingface.co |
| `GET /llm/search/{repo:path}` | quant list with exact sizes, exact badge after the header read | huggingface.co |
| `POST /llm/install` | NDJSON progress, existing `_event()` frame shape | huggingface.co |
| `DELETE /llm/models/{model_id:path}` | `ModelDeleteRead`, `selection_cleared` | none |

`GET /llm/search/{repo}` is where the 2–4 MB header read happens, so the trigger
is **opening a search result**, not hovering or typing. The list-level badge
stays `approximate` until then.

Deleted with the Ollama adapter: `GET /llm/providers/{provider}/catalog` and
`POST /llm/providers/{provider}/pull`. Both are Ollama-shaped, and their
replacements are the rows above.

Unchanged: `GET /llm/providers`, `GET|PUT /llm/selection/{role}`,
`GET|POST /llm/onboarding`, and everything under `/llm/connections`.

### Identifiers

| | Value |
|---|---|
| Registry key and `selected_models.provider` | `"llamacpp"` |
| Alembic revision for 7.6 | `0012` (head is `0011_document_cancelled_status`) |
| Egress destinations | `model_download`, `model_search` (both `huggingface.co`) |

`"ollama"` appears at **18 non-test Python sites**; each becomes `"llamacpp"` or
is deleted with the adapter.

### Out of scope

Local image generation is untouched. `modules/llm/router.py` carries four image
routes (`/image/local`, `/image/local/runtime`, `/image/local/{name}`,
`/image/local/{name}/install`) and `resolve_image_generation()` dispatches on
`sdcpp.PROVIDER` through `OpenAICompatibleImageProvider`. None of that changes,
and the sd-server sidecar keeps its own lifecycle. The only shared file is
`modules/llm/router.py`, which is edited around them.

Also unchanged: ingestion, the bge-small 384-dimensional index, retrieval, the
chat SSE protocol, Kokoro, and the OpenAI-compatible connection path.

### Constants: what v1 carries, and what it deliberately does not

A constant here is a fixed number compiled into the fit path. Not user-facing,
not per-machine: decided once, written down, and wrong for everybody if wrong at
all. Earlier drafts of this phase needed five. **v1 carries one.**

**Prediction constants are not runtime constants.** Almost everything below only
decides what the screen says. `--fit` does its own allocation at load and moves
layers if our sum was optimistic, so an inaccurate prediction produces a wrong
*label*, not a broken model. The single exception is the context floor, which is
passed to the runtime as `-c` and genuinely changes behaviour — which is why it
is derived from the codebase rather than chosen.

#### In v1

| Constant | Kind | Basis |
|---|---|---|
| **Context floor, 16K** | **runtime** | `HISTORY_BUDGET_TOKENS = 3000` plus ~8,000 tokens of grounding (~24k characters from `build_context`) plus a reply. Grounded, not chosen. |
| **Runtime overhead** | prediction | Pre-model half **measured at 986 MiB** on a discrete card; the per-model half is a bootstrap value, replaced by the machine's own measurement after its first load. See below and **7.2**. |

> **ponytail: runtime overhead.** The `overhead` term in
> `need = weights + KV(window) + overhead` is a placeholder. Hermes uses
> `max(2 GiB, 9% of total)` (`_MARGIN_FLOOR = 2 << 30`, `_MARGIN_FRACTION = 0.09`
> in `local_runtime/hardware.py`), which on a 6 GB card holds back a third of it;
> today's `recommendation_reserve_gb: 2.0` is self-flagged as uncalibrated. On a
> 5.4 GB budget the difference between 1.0 and 2.0 GiB moves rows across the
> `FITS`/`PARTIAL` line, and on a 12 GB
> NVIDIA card it decides whether Qwen3 14B is recommended at all (31 MiB of
> margin at 1,024 MiB overhead). **Measure real RSS after loading three or four
> models on each target before 7.4 ships**, and ship that as the bootstrap
> value — but it is wrong at most once per machine, because 7.2 records what the
> load actually cost and prefers that number afterwards.

#### Not in v1, and why

Each of these was in an earlier draft. Each was dropped because it would have
meant writing an invented number into a spec where it would be indistinguishable
from a measured one. That is the specific failure this phase exists to avoid:
llmfit called Qwen3 8B a "Perfect" fit for an 8 GB Mac because it was working
from a memory figure that was not true on that machine.

| Constant | What it would enable | Why not now | What it needs first |
|---|---|---|---|
| `felt_cost` | a formula predicting how slow a model *feels* on this machine | the recommendation is "highest `rank` that fits"; no latency judgement is made | a prefill model — `llama-bench pp512` per device class. llmfit's `prefill_tps` is an estimate for a generic machine. |
| **Speed floor** | refusing to star a model that fits but crawls | same | a `felt_cost` that means something, plus a threshold from real sessions rather than copied from an agent app |
| **Ladder rungs** | starting narrow so a **bigger model stays GPU-resident**, widening only when a conversation needs it. The benefit is memory, not long chats: Qwen3 4B on an 8 GB M2 is `FITS` at 16K and `PARTIAL` at 40K, purely from KV cache. | context is fixed at load | evidence that mid-conversation reloads are worth the complexity for document Q&A |
| **Growth threshold** | when to step up a rung | same | measured occupancy over real sessions |
| `decode_fraction` | correct speed prediction for mixture-of-experts models | **nothing to apply it to** — no MoE entry ships in v1. The value itself is computable today, from `expert_used_count` and the tensor table. | only the 80B-A3B-class rung |

#### When they come back

Each is additive and none requires a migration or a contract change.

- **The speed gate** (`felt_cost` + floor) lands with the first real prefill
  measurements. It slots into the recommendation policy as a filter over the
  `FITS` set; the ordering and the badges are untouched. The reasoning about
  *why* it must measure prefill and not decode is kept under the policy block so
  it is not rediscovered.
- **The context ladder** (rungs + threshold) lands if fixed-at-load proves
  limiting on large machines. It changes `POST /models/load` timing only.
- **`decode_fraction`** lands with the MoE rung, as a manifest field that
  defaults to `1.0` for every dense entry already shipped.

Shipping without them is not a gap to apologise for. Four of the five were
numbers nobody had measured, and a confident wrong badge is worse than a narrower
feature that tells the truth.

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

`modules/llm/gguf/header.py`, stdlib only. Local file or `Range: bytes=0-8388607`
against `huggingface.co`. Yields architecture, `block_count`, `context_length`,
`embedding_length`, `head_count_kv`, key/value lengths, `sliding_window`,
`expert_count`, `n_vocab`, chat template, exact tensor bytes.

Verified: HF returns `206` with `accept-ranges: bytes`. A 135M model's metadata
ends at 1.77 MB and its tensor table at 1.79 MB, in 2.5 s. **Bigger models need
more:** Qwen3-Coder-30B-A3B's metadata alone runs to 5.94 MB, with 579 tensor
entries after it, so a 4 MB budget fails on it. Budget **8 MB** and retry wider
on a truncated parse. The vocabulary token list is what makes the metadata
large, so the figure scales with vocab size rather than with the model.

**Tests:** a checked-in truncated GGUF; a fake HTTP server asserting the Range
header and a truncated-response retry.

### 7.2 — Hardware budget and estimator

`modules/llm/hardware.py` — `ctypes` into `libggml`, then `--list-devices`, then
OS APIs. First hit wins, cached; warm the probe in the background at first
launch, not on the path of the first render (a cold `ggml_backend_load_all()` on
macOS compiles 20 Metal shader libraries, measured at ~20 s once, 180 ms after).
That cold penalty is **Metal-only**: measured off Apple Silicon the same call is
77 ms with one backend and 205 ms with two.

#### The probe must run from the library directory

**This is the single most likely way this phase ships broken.**
`ggml_backend_load_all()` discovers backends by scanning **the directory of the
running executable**, not the directory the libraries were loaded from. The
backend probe runs inside the frozen `surfsense-api.exe`, which lives in
`resources/backend/`; the ggml libraries live in `resources/llamacpp/`. Different
directories, so the scan finds nothing.

Verified on a Windows machine with a working RTX 3050, same minute, same process
otherwise:

```text
python wprobe.py                      →  device count 0     ← card invisible
cd <llamacpp dir> && python wprobe.py →  device count 2     ← CUDA0 + CPU
```

**Loading the libraries by absolute path is not sufficient.** The backend scan is
a separate step keyed on the host executable. Set the working directory around
`ggml_backend_load_all()`, or spawn the probe from the library directory.

`GGML_BACKEND_PATH` is **not** the escape hatch — it expects a *file*, not a
directory. Passing one logs `load_backend: failed to load <dir>` and leaves the
count at zero.

The failure is silent and indistinguishable from a genuinely GPU-less machine:
every row badges *"Works here, runs on your processor"* and nothing reports an
error. See **Failure behavior**.

#### Two library handles on Windows, one on Linux

The exported symbols are split, and the intuitive single handle fails:

| Library | Exports |
|---|---|
| `ggml.dll` / `libggml.so` | `ggml_backend_load_all`, `dev_count`, `dev_get` |
| `ggml-base.dll` / `libggml-base.so` | `dev_name`, `dev_description`, `dev_type`, `dev_memory` |

Linux resolves the second through the ELF dependency, so one
`CDLL("libggml.so")` works — but `CDLL("libggml-base.so")` raises `undefined
symbol: ggml_backend_load_all`. **Windows needs both handles**; PE exports do not
chain, and `ggml.dll` alone raises `AttributeError: function
'ggml_backend_dev_name' not found`.

#### Device selection: first `type == GPU`, never a sum

A machine reports one entry per *(backend, device)* pair, so the same physical
card can appear more than once and an integrated GPU can advertise more memory
than a discrete one. Measured:

```text
[0] Vulkan0  type=GPU    6002.0 MiB total, 5234.0 MiB free   NVIDIA GeForce RTX 3050
[1] Vulkan1  type=ACCEL 16198.3 MiB total                    AMD Radeon(TM) Graphics
[2] CPU      type=CPU   31884.6 MiB total, 22750.2 MiB free  AMD Ryzen 5 9600X
```

```python
def select_device(devices):
    """First GPU wins. ggml orders backends by preference, so this is also
    backend selection."""
    return next((d for d in devices if d.type == DeviceType.GPU), None)
```

- **First, not largest.** Sorting by memory picks the 16 GB integrated chip over
  the 6 GB discrete card and places every layer on the slower device.
- **Never aggregate.** No `sum()` across devices. One device becomes
  `HardwareBudget.usable_vram_bytes`.
- **`ACCEL` is not a GPU** for budgeting — an integrated part carving from system
  RAM has no memory of its own to place layers in.

This rule is required here, under Vulkan alone. It becomes load-bearing if
[`08-cuda-backend.md`](08-cuda-backend.md) ever ships, because two loaded
backends list the same card twice, **both typed `GPU`**, so type filtering does
not deduplicate them.

#### `ram_available_bytes` does not come from ggml reliably

ggml's CPU device reports real available memory on native Windows (31884.6 MiB
total against 22750.2 MiB free, measured) but **`total == free` under WSL2**,
where the figure is virtualised. Keep the OS API in the chain for the RAM half
rather than trusting the CPU device, since `ram_available_bytes` is what
separates `PARTIAL` from `TOO_BIG`.

Two budget modes. **Capacity** (total − margin) for catalog pricing; **live**
(free now) for launch decisions. Pricing against live-free while a model is
loaded makes every row read as too large.

`modules/llm/fit.py` — `weights + KV(window) + overhead` vs `VRAM + RAM`.
Per-layer KV from the header. Split today's single `recommendation_reserve_gb: 2.0`
(flagged `ponytail` as uncalibrated) into a measured runtime overhead, a device
margin, and a UMA headroom.

> **Do not double-count.** ggml's `free` **already excludes** the desktop's
> allocation and the backend context. Measured on a 6144 MiB RTX 3050: 986 MiB
> was gone before a single weight loaded — ~445 MiB to the desktop, ~541 MiB to
> the CUDA context (`nvidia-smi` idle free 5699 MiB against ggml's 5158 MiB).
> Budget from `free` **and** add a ~1 GiB overhead term and the same memory is
> charged twice, demoting rows that fit. State explicitly which number `margin`
> and `overhead` are each subtracted from: against `free`, `margin` is ~0 and
> `overhead` covers per-model compute buffers only.

> **ponytail:** the *per-model* half of the overhead constant is still a
> placeholder until measured against real RSS with a model loaded. The
> pre-model half is now measured at 986 MiB on a discrete card. On a 5.4 GB
> budget it moves rows across the fits/spills line.

#### The overhead constant is a bootstrap value, not a permanent guess

The shipped constant is a prediction for a machine nobody tested. **After one
successful load, that machine's real figure is known**, and the same rule the
rest of this phase runs on applies: anything that differs per machine is measured
on that machine by the runtime that will do the work.

The instrument is already in use — `ggml_backend_dev_memory()`, sampled either
side of `POST /models/load`:

```python
real_overhead = (free_before - free_after) - weights_bytes - kv_bytes(n_ctx)
```

```text
first run         predict with the shipped constant
after first load  record the machine's real overhead, keyed by device name
every run after   prefer the recorded value
```

Three reasons this is worth ~15 lines in the load path:

- **The constant is wrong at most once per machine**, on a screen shown before
  anything is installed, instead of wrong forever on every machine that was not
  one of the three targets.
- **It self-corrects per backend and per driver.** A CUDA context alone costs
  ~541 MiB (measured); Metal and Vulkan differ; a driver update changes it. A
  committed table cannot track that and no longer has to.
- **It retires the last `ponytail` in the fit path.** Nobody repeats the
  measurement session after the first release.

Storage is a small JSON file in the app data dir keyed by device name — no
migration, and no settings table needs inventing for it. Invalidate on a
llama.cpp build bump or when the device name changes.

**Tests:** a recorded value is preferred over the constant; a recorded value from
a different device name or build is ignored; a corrupt or missing file falls back
to the constant rather than raising, since this sits on the first-render path.

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
data dir so nothing writes to `~/.cache`).

**Context is fixed at load, not grown.** `POST /models/load {"args": ["-c", N]}`
with `N` the largest window that keeps the verdict at **`FITS`** — not the
largest that fits at all. KV cache is allocated upfront and competes with the
weights for device memory, so maximising context silently demotes models out of
GPU residency: Qwen3 4B on an 8 GB M2 is `FITS` at 16K (4,632 MiB) and `PARTIAL`
at its native 40K (6,468 MiB). Floored at 16K (3,000
history tokens plus ~8,000 of grounding plus a reply) and capped at the model's
own `context_length`. No ladder, no reload mid-conversation. Growing on
occupancy is additive later; it would mean reloading the model between turns and
two constants copied from Hermes with no evidence they suit RAG.

**Router mode runs with an empty models directory**, so the sidecar lifecycle is
testable before any model exists. Verified on Windows and Linux at `b11050`:
`GET /health` → `{"status":"ok"}`, `GET /models` → `{"data":[],"object":"list"}`,
and `GET /props` → `"role":"router"` — which is the reliable check that the
sidecar came up in router mode rather than single-model mode. SIGTERM shuts it
down cleanly (`cleaning up before exit`), and on Windows `taskkill /PID <pid> /T
/F` walks the tree and reports each child terminated.

> **Partially verified only.** The `taskkill /T` check above ran with no model
> loaded, so it reaped `conhost.exe` rather than a model worker. The case 7.5
> actually cares about — reaping the **grandchild** the router spawns per loaded
> model — still needs a run with a model resident.

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

  // ── DERIVED, per model. The script writes all of this, no human input ever.
  //    Quantization-independent: measured, the architecture fields are
  //    identical across Q4_K_M, Q8_0 and f16 of the same model.
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
  "decode_fraction": 1.0,       // 1.0 dense; the active slice for MoE, computed
                                // from the header (see below)

  // ── One entry per shipped build. v1 ships exactly one.
  "variants": [
    {
      // DERIVED
      "repo": "unsloth/Qwen3-8B-GGUF",
      "file": "Qwen3-8B-Q4_K_M.gguf",
      "quantization": "Q4_K_M",
      "size_bytes": 5027784512,
      "mmproj": null,

      // JUDGEMENT. Three fields, typed by a person, beside the build they judge.
      "rank": 78,                     // preference order for document Q&A.
                                      // Not a benchmark. Never displayed.
      "rank_basis": "llmfit-1.1.11",  // what produced it
      "validated": true               // someone ran THIS file
    }
  ]
}
```

**The split is the point.** Everything marked DERIVED comes free from the GGUF
header and the Hugging Face listing; everything marked JUDGEMENT is three small
decisions a person makes in a minute. That is what keeps the manifest
maintainable at twenty entries instead of six — the tedious half scales
automatically, the half that needs a brain stays tiny.

**Why `rank` lives inside the variant.** Quality is a function of *(model,
quantization)*, not of the model alone: llmfit returns 75 · 78 · 81 · 82 · 83 for
Qwen3 8B at Q3_K_M · Q4_K_M · Q5_K_M · Q6_K · Q8_0 (see **Appendix**). A rank at
the top level therefore describes a build without naming it, and that is not
hypothetical — an earlier draft of this document carried five ranks taken at
Q8_0 while the manifest pinned Q4_K_M, and nothing in the schema could catch it.
Nested, the mismatch is **impossible to express**: the rank sits beside the
quantization it was measured at, and `test_curated_models.py` asserts the pair
mechanically instead of a person remembering a rule.

`rank_basis` records what produced the number — `llmfit-<version>` today, an
internal eval identifier later. It exists so a manifest part-way through that
migration is detectable, and so ranks from different bases are never compared.

**`variants` is a list from the start, and v1 puts one thing in it.** Authoring
is unchanged: one pin, one rank, the same twenty minutes. The list costs nothing
now and is the only part of this schema that is expensive to add later, because
changing it means `schema_version: 4` and re-authoring every entry. It also
closes the gap named first under **The quantization ladder**: with two variants a
24 GB card and a 64 GB machine stop receiving the identical file. The ladder
sweep in **Authoring** already computes a rank for every rung and discards four
of five; this is where the rest would go.

**`shape` is what makes the curated tier work offline.** Pricing a model means
reading its GGUF header, and a curated entry is not downloaded yet — so without
these fields an airgapped machine has no fit badge on the one tier it can use.
Committing what the header said at authoring time is what lets `weights +
KV(16K) + overhead` run against the manifest alone, on first paint, with no
network. It is the same reason Hermes carries estimator inputs inline.

`decode_fraction` is the fraction of the build's bytes read per decoded token:
`1.0` for a dense model, the active slice for MoE. **It is computed, not typed.**
The header carries `<arch>.expert_count` and `<arch>.expert_used_count` (verified:
128 and 8 on Qwen3-Coder-30B-A3B), and expert tensors are identifiable in the
tensor table the reader already parses — `blk.N.ffn_{down,gate,up}_exps.weight`,
144 of that model's 579 tensors. So:

```
decode_fraction = (non_expert_bytes + expert_bytes × used_count / expert_count)
                  ÷ total_bytes
```

Sanity check: Qwen3-Coder-**30B-A3B** is 30B total against 3B active, so the
formula should land near 0.1, which is the range Hermes hand-authored (0.08 to
0.15) for comparable models. Without it an MoE entry's speed
prediction is wrong by an order of magnitude, which matters the moment the
80B-A3B-class rung lands.

`decode_fraction` stays **per model, not per variant**: it is an expert-to-total
byte ratio, so it barely moves with quantization. `shape` and `capabilities` are
per-model for the same reason — the architecture fields are identical across
quantizations, measured.

`validated: true` means a person downloaded **that variant's** file and ran it.
False is allowed and honest; it is not a gate. Per-variant is the only place it
means anything precise once an entry ships more than one build.

Dropped from v2: `artifacts` (replaced by `variants`, which can hold more than
one), `minimum_fit` (a gate — only physics gates now), `allowed_quantizations`
(redundant once a variant names its file), `minimum_context` (the model's own
`context_length` replaces it), and top-level `advisor_providers` (scoped an
llmfit scan that no longer runs).

#### Authoring

A script run by hand, **never CI**. The manifest is **source, not build output**.

```bash
$ uv run scripts/refresh_curated_models.py \
    --add Qwen/Qwen3-Next-80B-A3B \
    --repo unsloth/Qwen3-Next-80B-A3B-GGUF --quant Q4_K_M

  resolving unsloth/Qwen3-Next-80B-A3B-GGUF … Q4_K_M found, 45.2 GB
  reading GGUF header (8 MB range) … qwen3next, 48 layers, 2 kv-heads, ctx 262144
  llmfit … sweeping budgets for the quantization ladder
          Q3_K_M 88 · Q4_K_M 94 · Q5_K_M 96 · Q6_K 97 · Q8_0 97
          pinned quant Q4_K_M found in ladder ✓
  llmfit proposes rank 94  (would be highest in the list — currently 92)
          writing variants[0]: Q4_K_M, rank 94, basis llmfit-1.1.11

  MoE detected: 128 experts, 8 used → decode_fraction 0.09
  ⚠ validated=false until you run this file.

  wrote curated-models.json (+1 entry)
```

The person then downloads it, chats with it, confirms citations resolve, sets
`variants[0].validated: true`, and commits. Twenty minutes, most of it
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

#### Scoring at the pinned quantization

**llmfit has no flag for this, so the script has to work for it.** There is no
way to ask for a score at a named quantization: `recommend` and `info` grade
whatever `best_quant` the detected hardware selects, and `plan --quant` accepts a
quantization but returns only `weight_gb`, `kv_cache_gb`, `total_vram_gb`,
`estimated_tps` and `recommended_gpu` — **no quality field**. Verified on
`1.1.11`.

That matters because quality tracks `best_quant` exactly (see **Appendix**).
Score at the wrong budget and you have graded a different file than the one in
`artifacts`. Qwen3 8B is 78 at the pinned Q4_K_M and 83 at Q8_0; run the script
on a workstation and you commit 83 for a file that behaves like 78.

**The procedure: build the model's ladder, then index into it.** Do not search
for a single budget. Sweep the device budget across the model's whole
quantization ladder, record the `(best_quant → quality)` pair at each step, and
look up the pinned quantization in the resulting map.

```
for budget in multiplicative_steps(lower, upper, ratio=1.01):
    row = llmfit recommend --force-runtime llamacpp --no-dashboard \
                           --memory {budget} --ram 128G -n 20000
    ladder[row.best_quant] = row.score_components.quality

variant.rank       = ladder[pinned_quant]   # KeyError is a hard failure
variant.rank_basis = f"llmfit-{llmfit_version}"
```

Because the rank is written **into the variant**, it is stored beside the
quantization it was read at and cannot drift from it. The `best_quant` assertion
below is what catches a bad *read*; the schema is what prevents a bad *write*.
Adding a second variant later means indexing the same ladder at a second rung —
the sweep already computed it.

Three properties this needs, each learned from a measured failure:

- **Multiplicative steps at 1 % or finer.** The window in which a given
  quantization is `best_quant` scales with the model, so fixed steps are wrong at
  both ends. Qwen3 0.6B reads `Q3_K_M` at 1400M, `Q4_K_M` at 1420M and `Q5_K_M`
  at 1500M — a Q4_K_M window roughly 6 % wide, which a 1G-step sweep skips
  entirely and silently. Qwen3 32B's is 22G to 24G, with 21G reading Q3_K_M and 25G reading Q5_K_M.
- **`--ram` pinned high and constant.** It is swept as one variable, not two.
- **A missing rung is a hard failure, never a fallback.** If the pinned
  quantization never appears in the ladder, the script **exits non-zero and says
  so**. It must not fall back to the nearest rung or to the bare-hardware score:
  that is precisely the silent mis-grade this section exists to prevent. The
  operator then types the rank by hand, which is always allowed.

The `best_quant` assertion in the transcript above is the visible half of this.
The ladder sweep is what makes it something the script can actually assert
rather than something the operator has to remember.

> **ponytail:** this whole subsection is a workaround for a missing llmfit flag.
> If `plan --quant` ever grows a quality field, or `recommend` grows
> `--quant`, the sweep collapses to one call and this text should be deleted
> rather than kept for history.

Numbers are source rather than build output for three reasons beyond speed: a
rank moving 78 → 94 appears in a pull request where someone notices, a tag
rebuilds to the same manifest forever, and the cadence is honest — these change
when someone adds a model, not when someone cuts a release.

#### Ranking

`rank` orders the curated rows and selects the ★. It does **two** things and
nothing else. It is never displayed, never compared outside the app,
and never applied to a searched model.

It is a property of a **variant**, not of a model: the same model at two
quantizations is two builds that answer differently, and the schema stores the
number beside the build. Where this section says "a model's rank", read "the rank
of the variant under consideration". With one variant per entry, as v1 ships, the
two readings coincide.

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
properly — the shipped six come back `33 · 48 · 63 · 78 · 85 · 92`, monotonic
and sanely spread — which is exactly the population the curated tier draws from.

> **Those figures are at the pinned Q4_K_M**, recovered by the ladder sweep
> above. An earlier draft of this document carried `38 · 53 · 68 · 83 · 90 · 92`,
> which is the same six graded at whatever `best_quant` a large budget selected —
> Q8_0 for five of them. The order was unaffected, so no pick or test changed,
> but the numbers described files the manifest does not ship. **Any rank quoted
> anywhere must name the quantization it was taken at.**

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

**One row per model, not per variant.** A model with two builds is one row; the
row takes the best state and rank among its variants, and the row's install
action uses that variant. Listing builds separately would show the same model
twice on a screen whose job is choosing a model.

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
resident = (entry, variant) pairs whose state is FITS
resident → max(variant.rank, -variant.size_bytes)   reason: best-rank-resident
else     → no recommendation; PARTIAL pairs stay installable,
                                just never starred
```

```python
candidates = [(e, v) for e in curated for v in e.variants
              if fit(e.shape, v.size_bytes).state is FitState.FITS]
pick = max(candidates, key=lambda ev: (ev[1].rank, -ev[1].size_bytes),
           default=None)
```

**The policy ranges over builds, not models**, because that is what the user
installs and what `rank` describes. With v1's single variant per entry the
cross-product is the entry list and the behavior is identical — but writing it
this way now is the difference between adding a `Q6_K` build later as a manifest
edit and rewriting the policy, its test file and every fixture. A model whose
larger variant is `TOO_BIG` and whose smaller one `FITS` is still recommendable
on its smaller build; that falls out of the cross-product rather than needing a
special case.

**No speed gate in v1.** An earlier draft gated on predicted latency, which
required two constants with nothing measured behind them. The policy is now
"highest rank among the entries that fit entirely on the device", and the tie
break prefers the smaller build, which leaves more room for context.

The gate is additive later. What it needs first is a prefill model: a handful of
`llama-bench pp512` runs per device class, since llmfit's `prefill_tps` and
`ttft_ms` are estimates for a generic machine and this app is prefill-dominated.

> **Why prefill, when the gate lands.** `HISTORY_BUDGET_TOKENS = 3000` plus ~24k
> characters of grounding is roughly 8,000 prefill tokens against ~300 decoded,
> the inverse of an agent's ratio. Decode is memory-bound; prefill is
> compute-bound. A decode-only prediction mis-ranks for this app.

> **RAG is prefill-dominated.** `HISTORY_BUDGET_TOKENS = 3000` plus ~24k
> characters of grounding is roughly 8,000 prefill tokens against ~300 decoded —
> the inverse of an agent's ratio. Decode is memory-bound; prefill is
> compute-bound. (An earlier draft cited a 36–40% CUDA lead here; measured, it
> is **9.1%** — see [`08-cuda-backend.md`](08-cuda-backend.md).) Use llmfit's
> `prefill_tps`/`ttft_ms` from the manifest until measured class constants exist.

**Tests:** policy decision-table across the six hardware profiles above.

### 7.5 — Packaging, three targets

`fetch-llamacpp.mjs`, pinned build number **and SHA-256** (`fetch-llmfit.mjs`
verifies a checksum; `fetch-ollama.mjs` does not — close that gap here, since
llama.cpp has no stable channel).

| Target | Asset | Size |
|---|---|---|
| darwin-arm64 | `bin-macos-arm64.tar.gz` | 11 MB |
| win32-x64 | `bin-win-vulkan-x64.zip` | 31 MB |
| linux-x64 | `bin-ubuntu-vulkan-x64.tar.gz` | 30 MB |

Verified: the Vulkan archive is the CPU archive plus exactly one file
(`libggml-vulkan.so` / `ggml-vulkan.dll`), and all CPU micro-architecture
variants ship inside — 15 on Windows, 10 on Linux (the CUDA archive carries 14
on Linux, so the figure is per archive, not per platform). `ggml_backend_load_best()`
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
- No Vulkan loader: `dlopen` fails, backend skipped silently, CPU runs. (Not
  observed on Windows — `vulkan-1.dll` is present in `C:\Windows\System32` on a
  stock install, so nothing needs bundling there. Linux supplies it through
  `libvulkan1`; see 7.5.)
- **A GPU exists and ggml cannot see it: say so.** The silent skip above is
  correct when there is no GPU and wrong when there is one, and the two are
  indistinguishable from ggml alone — both print `(none)` and exit **0**, with no
  warning even under `GGML_BACKEND_DEBUG=1`. Two real causes: the probe ran
  outside the library directory (7.2), or a backend library's dependencies are
  missing from the package. Cross-check against the OS:

  | OS reports a GPU | ggml reports a GPU | Meaning |
  |---|---|---|
  | yes | yes | normal |
  | no | no | genuine CPU-only machine, badge accordingly |
  | **yes** | **no** | **broken install.** Say so; never badge CPU-only. |

  Sources: `Win32_VideoController` on Windows, `/sys/class/drm` on Linux. Filter
  virtual adapters — the test machine carried a `Parsec Virtual Display Adapter`
  beside two real GPUs. Odysseus codes around the same failure explicitly
  (*"nvcc found but CUDA runtime is not visible"*), which is independent evidence
  it is common enough to handle rather than assume away.
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
  display metadata, and each rejection path): every entry has a `shape` and at
  least one variant; every variant has a `quantization`, a `rank` and a
  `rank_basis`; every `shape.architecture` is in the 152-name list; a curated
  row prices and badges with no network at all. Note
  `test_packaged_manifest_has_eight_unique_curated_models` asserts `len == 8`
  and `advisor_providers == ["Alibaba"]` — both become wrong, and both are
  updated in the same commit as the manifest, never before.
- **A model with two variants is one row**, taking the best state and rank among
  them, and recommending the variant that produced them. Asserted with a fixture
  carrying a `TOO_BIG` large build and a `FITS` small one: the row is
  recommendable on the smaller build.
- **Ranks are never compared across `rank_basis` values.** A fixture mixing an
  `llmfit-*` rank with an eval-derived one is rejected rather than silently
  sorted.
- **`rank` rises with parameter count within a family.** Today this passes
  trivially — the shipped six are one family and score `33 · 48 · 63 · 78 · 85 ·
  92` at the pinned Q4_K_M. The first failure is the signal to look, and it is expected: a
  mixture-of-experts, a second dense family, or a specialist ranked for document
  Q&A rather than for what it was tuned on will all break size-ordering
  legitimately. The assertion exists to make that a decision, not a drift.
- **Authoring: every committed `rank` was taken at that entry's pinned
  quantization.** The ladder sweep records which rung it read; the script fails
  non-zero when the pinned rung is absent rather than grading a neighbour. This
  is a script-level test, not an app test — nothing in the product can check it,
  which is exactly why it is written down.
- A curated entry with a `vision` capability is never preferred over a
  higher-ranked text model for the ★; capabilities do not enter the ordering.
- Capabilities: `vision` requires **both** `IMAGE in inputs` and
  `typed_content`; a model with image input and a string-only template reports
  no vision badge. `supports_system_role` false routes the system message into
  the first user turn rather than dropping it. Only the user-facing set reaches
  the serialized response — `system_role` and `typed_content` never appear in
  an API payload.
- **Device selection**: `select_device()` over fixtures — a discrete 6 GB card
  beside a 16 GB integrated one selects the **discrete** card; `ACCEL` alone
  yields no GPU; `usable_vram_bytes` never exceeds any single device's memory
  (asserted against a listing where the same card appears twice, which a naive
  sum turns into 12 GB on a 6 GB card); a CPU-only listing returns `None`.
- **Library loading**: two `ctypes` handles on Windows, one on Linux. A
  regression is an `AttributeError` at startup, not a wrong answer, so it is
  worth an explicit test rather than leaving it to the first packaged run.
- **Probe working directory**: devices are found when the probe runs from the
  library directory and **not** found when it does not. The second assertion is
  what stops the search-path bug from returning; without it the test passes in a
  dev shell and the bug ships.
- **Broken-install detection**: the three OS-versus-ggml rows in **Failure
  behavior**; the mismatch row produces a distinct error state, never a
  `has_gpu: false` budget.
- Runtime: fake llama-server for health/models/props/load/chat/delete; router
  mode against an empty models directory, asserting `/props` reports
  `role: router`.
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
- A Windows machine with an RTX card runs on Vulkan, from the installer alone,
  and the catalog prices against that card rather than an integrated GPU.
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

**The same result on a single model, swept.** The population statistic above says
hardware does not move quality. This says *why*, and it is the observation the
whole authoring design rests on. Qwen3 8B, `--ram 64G` held fixed, sweeping the
device budget:

| `--memory` | `best_quant` | `quality` | `estimated_tps` | `score` |
|---|---|---|---|---|
| 6G | Q3_K_M | 75 | 17.9 | 65.1 |
| 7G | Q4_K_M | 78 | 13.4 | 63.8 |
| 8G | Q5_K_M | 81 | 10.7 | 63.6 |
| 10G | Q6_K | 82 | 9.0 | 66.2 |
| 12G | Q8_0 | **83** | 6.7 | 63.6 |
| 16G | Q8_0 | **83** | 6.7 | 67.4 |
| 24G | Q8_0 | **83** | 6.7 | 67.4 |
| 48G | Q8_0 | **83** | 6.7 | 67.4 |

Read the last four rows: 12 GB to 48 GB, four times the memory, and `quality`
does not move. **It stops moving the instant the quantization stops moving.**
Hardware reaches quality through exactly one channel, `best_quant`, and that
channel is one we close by pinning the file.

Three decisions follow from that, and this table is the reason for all three:

1. **`rank` is authored once and shipped frozen.** A number that does not vary
   with the machine is data, not a per-machine computation. There is nothing for
   a scan on the user's device to discover.
2. **Only `score_components.quality` is read; `score` is discarded.** In the same
   sweep `score` runs 65.1, 63.8, 63.6, 66.2, 63.6, 67.4 — non-monotonic, and
   moving with hardware because it blends fit and speed into the quality term.
   The composite is a statement about a laptop; the component is a statement
   about a file.
3. **The declared budget must land llmfit on the pinned quantization.** Since
   quality tracks `best_quant` exactly, scoring at the wrong budget scores the
   wrong file. See **Authoring**, where this is a hard assertion rather than a
   convention.

**Windows and Linux, measured on an RTX 3050 / Ryzen 5 9600X at `b11050`.**
Both platforms were previously reasoned from documentation only.

| Measurement | Value |
|---|---|
| `ggml_backend_load_all()`, one backend | 77 ms (Win) · 194 ms (Linux) |
| `ggml_backend_load_all()`, two backends | 205 ms |
| `ggml_backend_dev_memory()` first call, CUDA | 47.89 ms |
| `ggml_backend_dev_memory()` first call, Vulkan | 3.50 ms |
| `ggml_backend_dev_memory()`, CPU | 0.01 ms |
| RTX 3050, `nvidia-smi` idle | 6144 MiB total, 5699 MiB free |
| RTX 3050, ggml after context init | 6143.5 MiB total, 5158 MiB free |
| Consumed before any weight loads | **986 MiB** (~445 desktop, ~541 context) |
| CPU device, native Windows | 31884.6 MiB total, 22750.2 MiB free |
| CPU device, WSL2 | 26048.6 MiB total, **26048.6 MiB free** (virtualised) |
| `vulkan-1.dll` on stock Windows | present in `System32`, nothing to bundle |

GPU backend comparison, same card and model (Qwen3 4B Q4_K_M, `-ngl 99`):

| test | CUDA 13.4 | Vulkan | CUDA advantage |
|---|---|---|---|
| `pp512` | 1929.18 ± 8.84 | 1767.62 ± 1.43 | +9.1% |
| `pp8192` | 1537.12 ± 5.84 | 1394.77 ± 5.04 | +10.2% |
| `tg300` | 52.19 ± 0.22 | 51.13 ± 0.11 | +2.1% |

0.66 s on an 11 s turn, for 685 MB. Full working in
[`08-cuda-backend.md`](08-cuda-backend.md) — **Appendix**, including why the
earlier 36–40% figure was retired.

Asset sizes at `b11050`, verified against the live release: macos-arm64 11.2 MB,
win-vulkan 31.8 MB, ubuntu-vulkan 30.4 MB — the figures in **7.5** are accurate.

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
