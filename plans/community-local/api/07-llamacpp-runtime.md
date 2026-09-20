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
| **Gating** | Only physics refuses | `can_install = state != TOO_BIG`, and `TOO_BIG` *is* the physics refusal — `need` at the 16K floor exceeding usable VRAM **plus** RAM. No other fit level gates anything; `PARTIAL` installs like `FITS`. Eligibility (architecture, chat template, gated repo) blocks separately and is not a fit state. See **Fit states**. |
| **Catalog** | Two tiers — curated manifest, and Hugging Face search | Curated is the offline product and ships frozen. Search is a network feature that is simply absent airgapped. |
| **Fit estimate** | Our own, from the GGUF header | llmfit cannot score a model outside its database (`llmfit plan` states the precondition). Search needs an estimate anyway; once it exists, llmfit's is redundant *and* less accurate here. |
| **`rank`** | **Curated entries only. A searched model never carries one, from llmfit or anywhere else** | A preference order over models we tested, **for this app's job** — answering from the user's documents with citations that resolve — not general capability. An integer typed by a person, with llmfit proposing. Called `rank`, not `quality`, because it is only ever a sort key: nothing reads its magnitude, so it must not imply a measurement we do not have. Attaching one to an arbitrary repo attaches a base model's score to a derivative that behaves differently: of the top 100 GGUF repos by downloads, 38 match an llmfit entry, and those matches include `Huihui-Qwen3.8-27B-abliterated-GGUF` and `Qwen3.8-27B-Uncensored-GGUF` resolving to the base model's score. A wrong number people trust is worse than a blank they investigate. Search rows are **described, not judged**. |
| **Search order** | `sort=downloads`, descending | The only HF sort that behaves as a default. Presented as a popularity fact, never as an endorsement. See **Search ordering**. |
| **Fit badge** | **Every row, both tiers** | Fit is subtraction, not judgement — the opposite of `rank`. Coarse from file size in the search list, exact from the header on open, exact from `shape` offline for curated. Three states, no `unknown`. |
| **Recommendation** | Highest `rank` among entries predicted **fast enough**, not among entries that fit entirely | Residency is a mechanism; speed is the goal, and on small cards they disagree. Measured on an RTX 3050: Qwen3 4B spills ~20% and Qwen3 8B ~28%, and a user runs the 8B without noticing. A `FITS`-only rule stars a 1.7B on that machine while the owner is happily using the 8B. v1 approximates the gate with an offload-fraction ceiling; the roofline and its self-calibration follow. See **Recommendation policy**. |
| **Curated manifest** | **Stays, schema 3, authored by hand** | It is the whole product airgapped, the first-run default, and the only tier the recommendation reads. `scripts/refresh_curated_models.py` writes it; a person commits it; **llmfit never runs in CI**. |
| **Why `rank` can be authored at all** | Quality is a function of *(model, quantization)*, not of hardware | Measured twice: across 2,424 models at a fixed quant, quality differs 0/2424; and on one model swept 12G to 48G, quality does not move once `best_quant` stops moving. Hardware reaches quality through exactly one channel, the quantization, and pinning the file closes it. So the number is a property of a file, computable once and shipped as data, and a scan on the user's machine has nothing to discover. This is the load-bearing fact under the whole authoring design. See **Appendix**. |
| **Which llmfit field** | `score_components.quality` only. **`score` is discarded** | `score` blends fit, speed and context into quality, so three of its four terms describe a machine. In the same sweep it runs 65.1, 63.8, 63.6, 66.2, 63.6, 67.4 — non-monotonic and hardware-dependent. The composite is a statement about a laptop; the component is a statement about a file. Same reason `fit_level`, `memory_required_gb`, `estimated_tps` and `best_quant` are all read and thrown away. |
| **Scoring quantization** | The pinned one, found by a ladder sweep. A miss is a hard failure | llmfit cannot be asked for a score at a named quantization, and quality tracks `best_quant` exactly, so the budget decides which file gets graded. Qwen3 8B is **78** at the pinned Q4_K_M and **83** at Q8_0. See **Scoring at the pinned quantization**. |
| **Manifest validation** | Existing unit tests. **No new CI** | Pydantic (`extra="forbid"`, `model_validator`) plus `test_curated_models.py` already reject malformed manifests. A dead pin is a runtime failure, gracefully handled — CI cannot prevent a repo disappearing after the build anyway. `validated: true` is the real check, and it is a human one. |
| **Hardware budget** | `ggml_backend_dev_memory()` via `ctypes`, from the shipped libs | The allocator's own view. Falls back to `llama-server --list-devices`, then OS APIs. |
| **Downloads** | **SurfSense fetches the GGUF**, not `POST /models` | `llama-server` is a second process we do not proxy; an in-process fetch is the only place `egress.require()` actually holds. Also buys resume, checksums, and the header as the file lands. |
| **Quantization** | **One pinned file per entry in v1** | A pinned file is what "tested by SurfSense" can honestly claim. Per-machine selection is possible at no extra cost (one header read prices every quant), so a second variant on the largest entries is a cheap follow-on, not v1. See **The quantization ladder**. |
| **KV precision** | **`f16` when it fits, `q8_0` when it buys residency.** Symmetric `-ctk`/`-ctv` always | Measured: `f16` KV at a 16K window **cannot allocate** on a 6 GB card (`ErrorOutOfDeviceMemory`), while `q8_0` at the same depth runs. Quality is lossless either way. So the choice is not a global default but an output of the fit calculation — pay the precision cost only where it converts a spill into residency. Requires flash attention; see **Failure behavior**. **Conditional on per-model load args working** — see 7.3; if they do not, this decision degrades to one global choice. |
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
         │          need   = weights + KV(window) + compute_buffers
         │          usable = device_free − fit_reserve
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

> **This column excludes `compute_buffers` and predates the fit reserve**, so it
> under-states `need` by roughly 170 MiB at 16K and prices against raw free
> memory. `GPU` / `RAM` in the map below is therefore a simplification — the real
> output is an offload fraction, and the map shows it where measured.
>
> **The one row since measured came out a state worse than predicted, and it is
> the row that rewrote the recommendation policy.** Qwen3 4B on an RTX 3050 needs
> 4,858 MiB against `5,234 − 1,028 = 4,206 MiB` usable: `PARTIAL` at `f ≈ 0.20`,
> not `FITS` with 490 MiB spare. llama.cpp spilled 602 MiB of weights and 320 MiB
> of KV. Under a `FITS`-only rule that machine's ★ fell to **Qwen3 1.7B** — while
> its owner runs **Qwen3 8B** (`f ≈ 0.28`, computed) without noticeable lag. That
> contradiction is what moved the gate from residency to speed; see
> **Recommendation policy**.
>
> The other five rows are unverified predictions and are **not** re-derived here:
> applying a reserve measured once on a 6 GB Windows card to an M4 Max would be
> inventing numbers, which is the failure this phase exists to avoid. Re-derive
> each row when its hardware is measured.

What each machine gets:

```text
machine          0.6B 1.7B   4B   8B  14B  32B   →  recommended
M2 8 GB           GPU  GPU  GPU  RAM  RAM    —   →  Qwen3 4B     (831 MiB spare)
RTX 3050 6 GB     GPU  GPU  ~20% ~28%  RAM  RAM   →  Qwen3 8B     (f ≈ 0.28)
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

Per-model at load, decided by the fit calculation rather than fixed here:
`-c <window>`, `-fa on` and, when `q8_0` is chosen, `-ctk q8_0 -ctv q8_0`.
**Set both cache types or neither** — symmetric quantization enables the fused
flash-attention kernel, while a mismatched pair falls back to an unoptimised
path that exists for correctness only.

> **All four of those flags ride the same unverified mechanism.** The ponytail
> in 7.3 records that `POST /models/load` ignored `{"args": ["-c", "16384"]}`.
> It is written up as a context problem because context is what was measured,
> but nothing distinguishes `-c` from `-fa` or `-ctk`/`-ctv`: they are the same
> field on the same call. If the router turns out to honour flags only at
> startup, then **KV precision cannot be per model either**, and the Decisions
> row above degrades from "an output of the fit calculation" to one global
> choice made for whichever model is largest. Resolve the mechanism once and
> both decisions follow; do not resolve it for context alone and assume the
> rest.

`--sleep-idle-seconds` is not optional: measured at `b11050`, a model without it
self-evicted after roughly 30 s idle, which turns the second question of a
conversation into a reload.

> **Never pass an explicit `-ngl`.** `--fit` owns layer placement, and setting
> `n_gpu_layers` by hand **disables it**:
>
> ```
> common_fit_params: failed to fit params to free device memory:
>                    n_gpu_layers already set by user to 99, abort
> ```
>
> Measured at `b11050`: with `-ngl 99` the model then loaded **entirely on the
> CPU** — 478 MiB of VRAM touched on a machine with a working RTX 3050, no error,
> exit 0. It looks like it worked. This is the same silent-GPU-blindness class as
> the probe search path (7.2) and the missing-backend case in **Failure
> behavior**, and it is the easiest of the three to introduce by accident, since
> `-ngl 99` reads as "use the GPU harder".

`--no-ui` because llama-server ships its own web UI. `--reasoning-format deepseek`
routes `<think>` blocks to `message.reasoning_content`; without it a thinking
model's trace enters `parts[]` and `resolve_citations()` rewrites `[n]` tokens
that appeared inside the reasoning.

## Contracts

> **Provenance.** The shapes and runtime calls below are grounded: the
> llama-server README at `b11043`, `nm` on the shipped libraries plus a live
> `ctypes` call, real GGUF headers read over HTTP Range, and live Hugging Face
> responses. **The HTTP routes below are proposed, not reported.** They follow
> this codebase's conventions: the `/llm` prefix, `*Read` Pydantic response
> models in `modules/llm/schemas.py`, and the NDJSON `{"type": …}` stream frame
> that `_event()` already emits.
>
> **Three of the six are not new paths, they are replacements at the same path.**
> `GET /llm/system`, `GET /llm/catalog` and `POST /llm/install` exist today, in
> `modules/llm/recommendations/router.py`, serving `RecommendationSystemRead`,
> `RecommendationCatalogRead` (with the `scanned` flag the renderer reads) and
> the same NDJSON install stream. So this is an **in-place breaking reshape, not
> an addition**: route, response schema and frontend have to move in one commit,
> because there is no additive path that does not serve two incompatible shapes
> at once. Only the two `/llm/search` routes and `DELETE /llm/models/…` are
> genuinely new surface.

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
    """One device, never a sum across devices. See 7.2 — device selection."""
    usable_vram_bytes: int    # device_free − fit_reserve. NOT raw free: llama.cpp's
                              # own fitter refuses to use the last slice, measured
                              # at 1,028 MiB of 5,234 free on an RTX 3050.
    total_device_bytes: int
    fit_reserve_bytes: int    # what was subtracted, carried so the badge can explain
    ram_available_bytes: int  # from OS APIs, not the ggml CPU device (see 7.2)
    uma: bool                 # unified memory: selects badge copy and headroom
    has_gpu: bool             # False when --list-devices prints "(none)"


class FitState(StrEnum):
    FITS = "fits"
    PARTIAL = "partial"
    TOO_BIG = "too_big"


@dataclass(frozen=True)
class FitVerdict:
    state: FitState
    need_bytes: int           # weights + KV(window) + compute_buffers
    budget_bytes: int         # usable_vram, or usable_vram + ram for TOO_BIG
    offload_fraction: float   # 0.0 fully resident … 1.0 all on the CPU.
                              # The recommendation gates on this, and the
                              # badge's reason line is graded by it. Do not
                              # collapse it into `state` — three buckets lose
                              # the difference between 5% and 70% spilled.
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

**Installing a searched build needs an id the manifest cannot supply.**
`InstallRequest` keys on `catalog_id`, and [`../frontend/05-install-ux.md`](../frontend/05-install-ux.md)
requires that the renderer send *only* that — no repo, file, artifact URL, local
path or quantization. A curated row's id comes from the manifest; a search hit
has no manifest entry, so there is nothing to key on. Closing that by letting the
renderer post a repo and file would hand the frontend the ability to name an
arbitrary download, which is the exact capability the install contract exists to
withhold.

So `GET /llm/search/{repo}` **mints a server-side install ticket per quant** and
returns it as that row's `catalog_id`, held with the same 300 s TTL as the search
cache. The install route then resolves tickets and manifest ids through one
lookup and cannot tell them apart. An expired ticket reuses the existing
`422 catalog id is stale or unknown; refresh the catalog` rather than inventing a
second staleness error, since it is the same failure and already has copy.

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

`"ollama"` appears at **115 lines across 24 non-test Python files**; each becomes
`"llamacpp"` or is deleted with the adapter. Counted across the whole tree it is
**421 lines in 66 files**, which is the figure 7.6 works from.

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
| **Fit reserve** | **runtime** | **1024 MiB, and not ours.** It is llama.cpp's `fit_params_target` default, one GiB per device on every backend, read from source and observed on both Vulkan and Metal. Pass it as `-fitt` rather than predicting it. See **7.2**. |
| **Compute buffers** | prediction | **Measured: ~170 MiB** for a 4B at 16K. Part of `need`, scales with context and batch. |

> **No longer a ponytail, and no longer a prediction.** The reserve began as an
> unmeasured placeholder at ~1,024 MiB. On an RTX 3050 `--fit` held back
> **1,028.34 MiB** of 5,234 free, which read as a lucky guess. It was not a guess
> and it was not lucky: `fit_params_target` defaults to `1024 * 1024*1024` per
> device in `common/common.h`, so the true figure is **exactly 1024 MiB** and the
> Windows excess was allocator rounding. Confirmed independently on Metal, where
> the fitter prints `cannot meet free memory target of 1024 MiB`.
>
> **So the generality worry was unfounded and the table it motivated is gone.**
> One point could not distinguish a constant from a proportion, which was a fair
> objection; the answer is that the source says constant. Hermes' equivalent is
> `max(2 GiB, 9% of total)` (`_MARGIN_FLOOR = 2 << 30`, `_MARGIN_FRACTION = 0.09`
> in `local_runtime/hardware.py`), roughly twice as conservative, and it is
> *their* number rather than the runtime's, which is the difference that matters:
> ours is the one the allocator will actually apply, and `-fitt` lets us set it.

#### Not in v1, and why

Each of these was in an earlier draft. Each was dropped because it would have
meant writing an invented number into a spec where it would be indistinguishable
from a measured one. That is the specific failure this phase exists to avoid:
llmfit called Qwen3 8B a "Perfect" fit for an 8 GB Mac because it was working
from a memory figure that was not true on that machine.

| Constant | What it would enable | Why not now | What it needs first |
|---|---|---|---|
| `felt_cost` | a time estimate replacing v1's crude `MAX_OFFLOAD` ceiling | the roofline is specified under **Recommendation policy**; v1 ships the ceiling because it fixes the observed failure with one number | its constants, which come from completed turns rather than a benchmark — see **Where the constants come from** |
| **Speed floor** | a threshold in seconds rather than in spilled fraction | same | a `felt_cost` that means something, plus a threshold from real sessions rather than copied from an agent app |
| **Ladder rungs** | starting narrow so a **bigger model stays GPU-resident**, widening only when a conversation needs it. The benefit is memory, not long chats: Qwen3 4B on an 8 GB M2 is `FITS` at 16K and `PARTIAL` at 40K, purely from KV cache. | context is fixed at load | evidence that mid-conversation reloads are worth the complexity for document Q&A |
| **Growth threshold** | when to step up a rung | same | measured occupancy over real sessions |
| `decode_fraction` | correct speed prediction, and the only way an MoE is priced sanely | it is an **input to the speed model**, which v1 approximates with `MAX_OFFLOAD`. Compute and commit it now regardless: it is free from the header, and `1.0` for every dense entry shipped. | nothing — this one is ready |

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

Phases 7.0–7.5 keep Ollama registered. `REGISTRY` carries both adapters, so each
ships independently and is reversible. **7.6 is the only irreversible phase and
the only one that touches user data.**

> **"Registered and working" is true of chat, not of catalog or install, and the
> difference is worth stating before someone plans around the stronger claim.**
> Two seams are llmfit-shaped and cannot serve both runtimes at once:
> `LocalRuntime.resolve(ScoredModel) -> InstallPlan` asks a runtime to map a
> *scored* model onto an install plan, and `LlamaCppProvider` has nothing to
> resolve because it installs a `GgufArtifact`; and `CatalogService.__init__`
> requires an advisor that 7.4 removes. So from 7.4 onward **Ollama's catalog and
> install path is dead even though its adapter is still registered**, and what
> survives to 7.6 is that an existing Ollama selection still answers, through
> `resolve_generation()` and the chat path.
>
> That is enough for the property the staging is for — no user loses chat
> mid-swap, and every phase before 7.6 reverts with one commit — but it is not
> "both runtimes fully working side by side", and trying to preserve that would
> mean keeping two catalog services alive for the sake of a runtime being
> deleted three phases later.

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

> **Most of this phase cancels itself out, so do not ship it on its own.** The
> `CACHE_VERSION` bump is pointless because 7.4 deletes `CACHE_VERSION` and the
> scan cache; retargeting the llmfit adapter is pointless because 7.4 moves
> llmfit out of the app, leaving `recommendations/llmfit.py` with no consumer.
> What genuinely survives is the **domain change** at the top of this section —
> `ollama_name` becoming `artifacts`, and the five deletions — plus the llmfit
> *parsing*, which becomes the authoring script's. Fold the rest into 7.4 and
> land them together rather than writing code whose only reader is deleted two
> phases later.

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

`modules/llm/hardware/` — `ctypes` into `libggml`, then `--list-devices`, then
OS APIs. First hit wins, cached; warm the probe in the background at first
launch, not on the path of the first render: on macOS, 20 Metal shader libraries
are compiled on the first call, measured at **19.0 s once** and ~45 ms after.
That cold penalty is **Metal-only**: measured off Apple Silicon the equivalent
call is 77 ms with one backend and 205 ms with two.

> **Warm the right call.** Earlier drafts attributed the cold cost to
> `ggml_backend_load_all()`. Measured on an M2, `load_all()` is **2.3 ms** and the
> compile happens inside the first **`ggml_backend_dev_count()`**, which is 19 s
> cold and 43 to 49 ms warm. A background warm that calls `load_all()` and stops
> therefore warms nothing, and the 19 s lands on whoever asks for the device list
> first, which is the first render. Enumerate the devices in the warm, not just
> load the backends.

> **Folders, not two files.** Earlier drafts named `hardware.py` and `fit.py`.
> Between them they carry library loading, the working-directory dance, device
> enumeration, device selection, the `--list-devices` fallback parser, OS memory
> APIs, the OS-versus-ggml cross-check, budget assembly, calibration storage, the
> KV term, compute buffers, the reserve table, the need/usable comparison, KV
> precision selection, context sizing and badge copy. That is sixteen
> responsibilities in two files, against the repo's one-responsibility-per-file
> rule in `AGENTS.md`. Split them along those lines; the names above are the
> package, not the module.

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
- **An integrated GPU is not a GPU** for budgeting — a part carving from system
  RAM has no memory of its own to place layers in. It types as `IGPU`, not
  `ACCEL`; see below.

> **The device type enum has five members, not three, and getting that wrong is
> a crash rather than a wrong answer.** Read from `ggml-backend.h` at `b11050`:
>
> ```c
> GGML_BACKEND_DEVICE_TYPE_CPU   = 0   // system memory
> GGML_BACKEND_DEVICE_TYPE_GPU   = 1   // dedicated memory
> GGML_BACKEND_DEVICE_TYPE_IGPU  = 2   // integrated, host memory
> GGML_BACKEND_DEVICE_TYPE_ACCEL = 3   // BLAS, AMX
> GGML_BACKEND_DEVICE_TYPE_META  = 4   // wraps several devices for tensor parallelism
> ```
>
> Earlier drafts of this document, and the listing in
> [`08-cuda-backend.md`](08-cuda-backend.md), label the integrated Radeon on the
> Windows machine `ACCEL`. Its raw type is `2`, so it is **`IGPU`**. The selection
> *behaviour* is unaffected, since both are skipped by `type == GPU`, and the
> reasoning was right about the hardware. Only the name was wrong.
>
> **A three-member Python enum crashes on macOS.** Every Mac lists an Accelerate
> `BLAS` device, measured at raw type `3`, so `DeviceType(3)` raises `ValueError`
> on a machine that is otherwise perfectly healthy. This is the probe running at
> first paint, so it is a startup failure, not a degraded badge. Model all five,
> and treat an unknown integer as "not a GPU" rather than as an error, because
> ggml has added a member twice and will again.

This rule is required here, under Vulkan alone. It becomes load-bearing if
[`08-cuda-backend.md`](08-cuda-backend.md) ever ships, because two loaded
backends list the same card twice, **both typed `GPU`**, so type filtering does
not deduplicate them.

#### `ram_available_bytes` does not come from ggml reliably

ggml's CPU device reports real available memory on native Windows (31884.6 MiB
total against 22750.2 MiB free, measured) and **nowhere else that has been
tried**. Under WSL2 the figure is virtualised and `total == free`. On macOS it is
worse: measured on an M2 with roughly 2 GB genuinely free, the CPU device reports
**8192.0 MiB total against 8192.0 MiB free** — physical RAM restated twice, with
no live component at all. The Metal device is barely better, at 5461.3 total
against 5461.0 free.

So **native Windows is the exception, not the rule**. Keep the OS API in the
chain for the RAM half rather than trusting the CPU device, since
`ram_available_bytes` is what separates `PARTIAL` from `TOO_BIG`, and treat a
`free == total` reading as "this device does not report live memory" rather than
as an idle machine.

Two budget modes. **Capacity** (total − margin) for catalog pricing; **live**
(free now) for launch decisions. Pricing against live-free while a model is
loaded makes every row read as too large.

#### Two subtractions, on opposite sides of the comparison

`modules/llm/fit/`. The single `overhead` term earlier drafts carried is **two
different quantities**, and collapsing them is what made the first prediction of
this wrong by 922 MiB:

```text
need   = weights + KV(window) + compute_buffers      what the model allocates
usable = device_free − fit_reserve                   what --fit will actually use
FITS  iff  need ≤ usable
```

Measured, Qwen3 4B Q4_K_M at 16K on an RTX 3050 with 5,234 MiB free:

| | MiB |
|---|---|
| `Vulkan0` model buffer | 2078.04 |
| `Vulkan0` KV buffer | 1984.00 |
| `Vulkan0` compute buffer | 143.62 |
| **placed on device** | **4205.66** |
| **left deliberately unused** | **1028.34** |

Treating that 1,028 MiB as part of `need` rather than as a subtraction from
available memory predicts `FITS` with 378 MiB spare. llama.cpp instead spilled
602 MiB of weights and 320 MiB of KV to the CPU — a `PARTIAL`. Same numbers,
opposite verdict, purely from which side of the comparison the term sits on.

`compute_buffers` was absent from the formula entirely. It is ~170 MiB for a 4B
at 16K (143.62 device + 26.01 host) and scales with context and batch, so it is
not a rounding error on a 6 GB card.

This replaces today's single `recommendation_reserve_gb: 2.0`, which was flagged
`ponytail` as uncalibrated.

#### The fit reserve is not a measurement. It is a flag we can set

**Corrected by reading the source and the log, on an M2 / 8 GB at `b11050`.**
Earlier drafts of this section carried a `(platform, backend, memory model)`
table with one measured row and two blanks, on the reasoning that Metal, Vulkan
and CUDA reserve different amounts and none of it transfers. **That reasoning was
wrong.** The reserve is a single hardcoded default in llama.cpp's own fitter,
identical on every backend:

```cpp
// common/common.h — margin per device in bytes for fitting parameters to free memory
std::vector<size_t> fit_params_target =
    std::vector<size_t>(llama_max_devices(), 1024 * 1024*1024);
```

**1 GiB per device, platform independent.** The Windows figure of 1,028.34 MiB
was that 1024 MiB plus 4.34 MiB of allocator rounding, so the spec's original
"~1,024 MiB" guess was not lucky to within 4.3 MiB, it was **exactly the
constant**. Metal names it out loud under `-v`:

```text
common_params_fit_impl: projected to use 5752 MiB of device memory vs. 5460 MiB of free
common_params_fit_impl: cannot meet free memory target of 1024 MiB,
                        need to reduce device memory by 1315 MiB
```

`5752 − (5460 − 1024) = 1316`. The comparison `need > free − 1024` is exact, on a
second backend, with no fitting.

**It is also a CLI flag: `-fitt` / `--fit-target`, in MiB, per device.** So the
reserve stops being a number to predict and becomes an input we control. Pass it
explicitly and `usable = device_free − fit_reserve` is true **by construction**
rather than by estimate, on every platform, including ones nobody has run.

| platform / backend | reserve | basis |
|---|---|---|
| any backend, any platform | **1024 MiB** | llama.cpp default, read from source at `b11050`; observed on Vulkan and Metal |
| whatever we pass to `-fitt` | that value | the flag exists; prefer pinning it to inheriting it |
| no GPU device | n/a | `PARTIAL` is unreachable; see **Fit states** |

**Three consequences.** The blank rows do not need measuring, and the plan to
measure them was work that could not have produced new information. The
self-calibration below is **no longer about the reserve**, only about the
compute-buffer half of the prediction. And pinning `-fitt` removes a class of
error rather than shrinking it, which is worth more than a better guess.

> **Errors here are still asymmetric, and the direction still matters** for the
> compute-buffer term that remains predicted. Too large predicts `PARTIAL` where
> reality is `FITS`: the user sees *Reduced speed*, installs anyway (`PARTIAL`
> installs exactly like `FITS`), and is not harmed. Too small predicts `FITS`
> where reality is `PARTIAL`, which is precisely the llmfit failure this phase
> exists to delete. *Unknown shapes round up; never underestimate memory.*

#### What `--fit` actually does when it cannot fit

Measured, same session, Qwen3 1.7B at `-c 40960` against a 5,460 MiB working set.
It does **not** solve for a placement, it **searches** for one, reloading at each
step:

```text
29/29 layers → 0/29 → 29/29 → 22/29 → 23/29   (settles at 23/29, f ≈ 0.21)
```

Two behaviours that matter to us fall out of that log:

- **It never touched the context.** KV stayed at 4,480 MiB / 40,960 cells through
  every step. Because `-c` was set explicitly, the fitter treats it as fixed and
  spills layers instead, which is the same "explicitly set means hands off" rule
  that `-ngl` follows. Good: our context floor survives contact with the fitter.
- **If we do not set `-c`, it will reduce context on its own, as far as
  `fit_params_min_ctx = 4096`.** That is well below our 16K floor and it happens
  silently. So `-c` is not optional for us, and not only because we want a
  particular window: leaving it unset hands the floor to llama.cpp.

Per-layer KV comes from the header; the formula is validated exactly in the
**Appendix**.

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

This residual **already contains the compute buffers**, which is why they need no
separate per-model table: the first load measures everything that is neither
weights nor KV, on the machine that will run it.

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

> **Resolved: `POST /models/load` cannot set per-model args. `--models-preset`
> can.** Measured on macOS at `b11050`. Every payload shape is accepted and none
> of them does anything: `{"args": ["-c","4096"]}`, `{"args":
> ["--ctx-size","4096","-fa","on"]}` and `{"preset": "..."}` all return
> `200 {"success":true}` while the worker's argv stays **byte identical**. The
> router reports that argv under `GET /models` as `status.args`, which is the
> only reliable way to see what it actually did.
>
> The mechanism is a separate flag, `--models-preset PATH`, pointing at an INI
> file with one section per model:
>
> ```ini
> [Qwen3-8B-Q4_K_M]
> model = /path/to/Qwen3-8B-Q4_K_M.gguf
> ctx-size = 16384
> flash-attn = on
> cache-type-k = q8_0
> cache-type-v = q8_0
> parallel = 1
> ```
>
> Verified: the worker then launches with `--ctx-size 16384 --cache-type-k q8_0
> --cache-type-v q8_0 --flash-attn on --parallel 1`, and reports the requested
> `n_ctx_slot` rather than its own default. **So every per-model decision in this
> phase is implementable**, including the KV precision row in **Decisions**,
> which rides the same mechanism as the context window.
>
> **The INI is read once at router startup.** Appending a section while the
> router runs does not surface the model, so installing a model or changing its
> load plan means rewriting the file and restarting the sidecar. That is the
> lifecycle `watchImageModel()` already implements for sd-server in
> `electron/src/main/index.ts`: poll a small endpoint, compare the arg set, then
> `stopNamed` plus `startOne` on a change. Reuse it rather than inventing a
> second supervisor pattern.
>
> Also measured and worth passing: llama-server defaults to `--parallel 4`, so
> the KV cache is sized for four concurrent slots this app never uses.

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

**The router costs no device memory until a model loads** (measured: VRAM
unchanged at the idle baseline with the router up and three models discovered),
and it **auto-discovers** everything in `--models-dir` as `status: "unloaded"`,
spawning one worker per loaded model with `--port 0 --model <path>`. Pass
`--sleep-idle-seconds` deliberately: at `b11050` a model self-evicted after
roughly 30 s idle without it, which would turn the second question of a
conversation into a reload.

**Router mode runs with an empty models directory**, so the sidecar lifecycle is
testable before any model exists. Verified on Windows and Linux at `b11050`:
`GET /health` → `{"status":"ok"}`, `GET /models` → `{"data":[],"object":"list"}`,
and `GET /props` → `"role":"router"` — which is the reliable check that the
sidecar came up in router mode rather than single-model mode. SIGTERM shuts it
down cleanly (`cleaning up before exit`), and on Windows `taskkill /PID <pid> /T
/F` walks the tree and reports each child terminated.

**Grandchild reaping verified**, with a model resident, on Windows at `b11050`:

```text
router          132  llama-server.exe
  child       10828  conhost.exe
  child        8820  llama-server.exe     ← the model worker
    grandchild 18688  conhost.exe

taskkill /PID 132 /T /F   →  all four terminated, depth first
SURVIVORS: none
```

> **Windows only.** macOS and Linux reap through process groups and signals, not
> `taskkill /T`, and the macOS hardened runtime case (7.5) is still untested
> against a grandchild.

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
KV(16K) + compute_buffers` run against the manifest alone, on first paint, with no
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

Four checks before committing a rank:

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

Let `need = weights + KV(window) + compute_buffers`, `vram` =
`HardwareBudget.usable_vram_bytes` (device free **minus** the fit reserve), and
`ram` = host memory available to the budget. The two subtractions sit on opposite
sides of the comparison and must not be collapsed into one term — see 7.2.

| State | Condition | What happens at load |
|---|---|---|
| `FITS` | `need ≤ vram` | every layer on the device, full speed |
| `PARTIAL` | `vram < need ≤ vram + ram` | `--fit` places some layers on the CPU; runs, slower |
| `TOO_BIG` | `need > vram + ram` at the **16K floor** | physics refusal — the only state that blocks install |

`TOO_BIG` is evaluated at the floor, not at the requested window: a model that
will not fit at 16K cannot be rescued by a smaller context, and the remedy to
offer is a smaller quantization or a smaller model.

**Keep `offload_fraction`, do not collapse it into the state.** `PARTIAL` spans
everything from barely-noticeable to unusable, and the number is already known
from the same subtraction that produced the state. Two consumers need it: the
recommendation gate, and the graded reason line below. Discarding it is what
made an earlier draft star a 1.7B on a machine happily running an 8B.

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

**Grade the `PARTIAL` reason line by `offload_fraction`.** Not optional: the
range is wide enough that one sentence is wrong at both ends, and the number is
already on the verdict.

```text
f ≲ 0.25   ◐  Reduced speed     A little too big for the graphics card. Most of it still fits.
f ≳ 0.5    ◐  Reduced speed     Well over your graphics card's memory. Expect it to be slow.
```

The verdict word does not change, because the state has not changed. Only the
explanation sharpens. An earlier draft filed this as a copy refinement; it is
really the same information the recommendation gate needs, surfaced.

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
eligible = (entry, variant) pairs that are not TOO_BIG
                            and whose offload_fraction ≤ MAX_OFFLOAD
eligible → max(variant.rank, -variant.size_bytes)   reason: best-rank-eligible
else     → no recommendation; every non-TOO_BIG pair stays installable,
                                just never starred
```

```python
candidates = [(e, v) for e in curated for v in e.variants
              for verdict in [fit(e.shape, v.size_bytes)]
              if verdict.state is not FitState.TOO_BIG
              and verdict.offload_fraction <= MAX_OFFLOAD]
pick = max(candidates, key=lambda ev: (ev[1].rank, -ev[1].size_bytes),
           default=None)
```

> **`MAX_OFFLOAD` fires, and it is load bearing.** An earlier draft suspected it
> might never trigger and should perhaps not ship. Run against the six profiles
> with the implemented estimator, the opposite holds: **without a ceiling, five
> of six machines star Qwen3 32B**, including a 6 GB RTX 3050 at `f = 0.82`.
>
> | machine | no ceiling | ceiling at 0.75 | `f` of the unceilinged pick |
> |---|---|---|---|
> | M2 8 GB | Qwen3 8B | Qwen3 8B | 0.38 |
> | RTX 3050 6 GB | **Qwen3 32B** | Qwen3 8B | **0.82** |
> | M4 16 GB | Qwen3 32B | Qwen3 32B | 0.57 |
> | RTX 4070 12 GB | Qwen3 32B | Qwen3 32B | 0.57 |
> | RTX 4090 24 GB | Qwen3 32B | Qwen3 32B | 0.05 |
> | M4 Max 64 GB | Qwen3 32B | Qwen3 32B | 0.00 |
>
> The earlier suspicion came from sweeping **one** model and finding every
> offload fraction usable. That is true, and it is the wrong population: the gate
> exists to stop the *largest* build being starred on a small card, and only the
> ladder exposes that.
>
> **0.75 is still too loose and should not ship as it stands.** It leaves the
> 4070 and the 16 GB Mac on a 32B at `f = 0.57`, which the roofline puts at about
> 37% of resident decode speed. Set the number from the roofline against a stated
> speed floor rather than picking a round one. The point here is only that the
> ceiling must exist.

`MAX_OFFLOAD` is a v1 placeholder for the speed gate below, not a latency
judgement. Set it generously: the failure it exists to prevent is starring a
model that crawls, and the failure it replaced was refusing models that work.

**The policy ranges over builds, not models**, because that is what the user
installs and what `rank` describes. With v1's single variant per entry the
cross-product is the entry list and the behavior is identical — but writing it
this way now is the difference between adding a `Q6_K` build later as a manifest
edit and rewriting the policy, its test file and every fixture. A model whose
larger variant is `TOO_BIG` and whose smaller one `FITS` is still recommendable
on its smaller build; that falls out of the cross-product rather than needing a
special case.

#### Why the gate is on speed, not on residency

An earlier draft gated on `FITS` alone, on the reasoning that a latency gate
needed constants nobody had measured. That is true and it still produced the
wrong answer, because **residency is a mechanism and speed is the goal.** They
coincide on a large card and diverge on a small one:

```text
RTX 3050, 6 GB, measured
  Qwen3 4B   f ≈ 0.20 spilled    →  PARTIAL
  Qwen3 8B   f ≈ 0.28 spilled    →  PARTIAL, and runs without noticeable lag
```

A `FITS`-only rule stars **Qwen3 1.7B** on that machine while its owner is
running the 8B perfectly happily. The rule is not conservative, it is wrong: it
bans a configuration that works.

The reason a fifth spilled is barely noticeable is that decode is
bandwidth-bound and the split is not proportional. Which is also why a single
threshold on `f` is a crude instrument, and why the real gate is a time estimate.

#### The speed model

Keep the offload fraction the fit calculation already computes. Decode reads the
weights once per token, so:

```text
f              = bytes_on_cpu / total_bytes      0.0 resident … 1.0 all CPU
t_token        = W × decode_fraction × ( f/BW_cpu + (1−f)/BW_gpu )
decode_tps     = efficiency / t_token
```

**Measured, and it holds.** Qwen3 4B on an RTX 3050, `-ngl` used to set `f`
directly so model size is held constant:

| layers on GPU | `f` | decode t/s | vs resident | implied `r` |
|---|---|---|---|---|
| 36/36 | 0.00 | **52.45** | 1.00 | — |
| 28/36 | 0.22 | 33.17 | 0.63 | 3.7 |
| 18/36 | 0.50 | 19.85 | 0.38 | 4.3 |
| 9/36 | 0.75 | 12.93 | 0.25 | 5.1 |
| 0/36 | 1.00 | 13.13 | 0.25 | 4.0 |

The slowdown reduces to `1/(f·r + 1 − f)` where `r = BW_gpu / BW_cpu`, and every
point fits **r ≈ 4** within ±20%. Cross-checked against absolutes: 131 GB/s
effective on the device (78% of the card's rating) against 33 GB/s on the host,
ratio 4.0. So `r` comes from published bandwidths and needs no per-card
measurement.

> **`r` is what makes spill tolerable here, and it is hardware-specific.** On a
> high-bandwidth card `r` is far larger — roughly 12 on a 4090 — so the same
> `f = 0.3` would cost ~78% rather than ~31%. Small cards have modest bandwidth
> *and* are the only ones that spill, which limits the damage, but a threshold
> calibrated on a 3050 is **not** conservative for other hardware. On unified
> memory `r` approaches 1 and spilling barely means anything.

**Prefill degrades roughly half as much as decode**, which matters more here than
anywhere because this app is prefill-dominated:

| `f` | prefill ratio | decode ratio |
|---|---|---|
| 0.22 | 0.81 | 0.63 |
| 0.50 | 0.67 | 0.38 |
| 1.00 | **0.50** | **0.25** |

Fully on the CPU, prefill still runs at half device speed while decode drops to a
quarter. A turn of ~8,000 prefill against ~300 decoded therefore loses
substantially less to spilling than any decode-focused benchmark implies — and
than Hermes' `PLEASANT_FLOOR_TOK_S = 20.0`, which was tuned for agentic bursts,
would suggest. **Do not import that threshold.**

`decode_fraction` is the manifest field already defined and computed from the
header — **this is the thing it is for.** The spec previously filed it as
"nothing to apply it to"; the speed model is the application.

Decode alone still mis-ranks for this app, because a turn is ~8,000 prefill
tokens against ~300 decoded. Prefill is compute-bound rather than
bandwidth-bound and degrades differently under offload, so it needs its own
term:

```text
felt_time ≈ prefill_tokens / prefill_tps  +  decode_tokens / decode_tps
eligible  = pairs whose felt_time ≤ budget
pick      = max(eligible, key=rank)
```

#### Where the constants come from: every turn is a measurement

`BW_gpu`, `BW_cpu`, `efficiency` and the prefill rate are per-machine. Both
reference implementations ship them as hardcoded tables — Hermes has a
`GPU_BANDWIDTH` dict and `_estimate_speed(..., offload_frac=0.0)`; Odysseus adds
`FALLBACK_K = {"cuda": 220, "rocm": 180, "metal": 150, …}`; llmfit's own output
admits `"method": "gpu_bandwidth_roofline"`, `"efficiency": 0.55`.

**We do not copy that.** A table of bandwidths for cards nobody tested is the
llmfit failure in a new costume. Instead:

> **A completed chat turn already carries everything the model needs** — prompt
> tokens, generated tokens, time to first token, total time — and the offload
> fraction of the loaded model is known. That is enough to solve for this
> machine's constants, with no benchmark, no extra binary and no user-visible
> step.

```text
first run      predict with a conservative shipped default
after turn 1   record (prompt_tokens, decode_tokens, ttft, total, f)
thereafter     predict with this machine's own numbers
```

Identical in shape to the memory self-calibration in **7.2**, and it reuses the
same per-device store. It is also why no `llama-bench` run ever has to ship.

#### Staging

| | |
|---|---|
| **v1** | Retain `f` on the verdict. Gate on an offload-fraction ceiling instead of `FITS`. One number, conservative, and it fixes the 3050 case. |
| **next** | The roofline above with a shipped default, plus badge copy graded by `f`. |
| **then** | Turn-based self-calibration, which retires the shipped constants. |
| **never** | A hardcoded per-GPU bandwidth table. |

The v1 step is deliberately crude: an `f` ceiling is not a latency judgement and
should not be described as one. It is a placeholder that is wrong in the safe
direction — it stars models that run, rather than refusing models that work.

> **RAG is prefill-dominated, which is why the gate must measure prefill.**
> `HISTORY_BUDGET_TOKENS = 3000` plus ~24k characters of grounding is roughly
> 8,000 prefill tokens against ~300 decoded — the inverse of an agent's ratio.
> Decode is memory-bound; prefill is compute-bound. A decode-only prediction
> mis-ranks for this app. (An earlier draft cited a 36–40% CUDA lead here;
> measured, it is **9.1%** — see [`08-cuda-backend.md`](08-cuda-backend.md).)
>
> **There is no manifest field to fall back on.** An earlier draft ended this
> block with *"use llmfit's `prefill_tps`/`ttft_ms` from the manifest until
> measured class constants exist"*. Those were `ScoredModel` fields, produced by
> a scan that no longer runs, and schema 3 carries `shape`, `capabilities`,
> `decode_fraction` and `variants` and nothing else. Until the turn-based
> calibration below lands there is a shipped default and no second source.

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
on Linux, so the figure is per archive, not per platform).

> **No CUDA payload ships, and the CUDA staging notes have moved.** Earlier
> drafts described the flat-folder probe order and the `cudart64_*` /
> `cublas64_*` / `cublasLt64_*` DLLs here, before the backend decision was made.
> This phase stages Vulkan on every platform off Apple Silicon and nothing else,
> so those notes belong to [`08-cuda-backend.md`](08-cuda-backend.md), which
> already carries them. Leaving them in a Vulkan-only packaging section reads as
> work to do.

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

421 references across 66 files. The only irreversible phase.

**Delete:**

```text
backend/modules/llm/providers/ollama/          provider.py, catalog.py, __init__.py
backend/tests/unit/llm/recommendations/test_ollama_runtime.py
backend/tests/unit/llm/test_ollama_num_ctx.py
electron/src/main/sidecars/ollama.ts
electron/scripts/fetch-ollama.mjs
electron/ollama/                               501 MB staged
```

**llmfit's packaging goes in the same phase**, and is easy to miss because none
of it has "ollama" in the name, so the definition-of-done grep below will not
catch a single one:

```text
electron/scripts/fetch-llmfit.mjs
electron/scripts/check-llmfit.mjs
backend/tests/fixtures/llmfit/                 fit.json, system.json
```

plus `SidecarContext.llmfitPath`, `python.ts`'s `SURFSENSE_LOCAL_LLMFIT_PATH`,
the four `llmfit_*` settings in `shared/config.py`, `recommendation_reserve_gb`
(replaced by the reserve table in 7.2), and the llmfit staging and smoke steps
in `release-local.yml`. **Decisions** says llmfit is not shipped and not in the
build; this is what that costs in files. `modules/llm/recommendations/llmfit.py`
itself is deleted earlier, in 7.4, when its parsing moves into the authoring
script.

**Rewrite:** `shared/config.py` (`ollama_base_url`/`ollama_models_dir` →
`llamacpp_*`), `sidecars/types.ts` (`SidecarContext.ollama*`),
`sidecars/python.ts` (stops passing `OLLAMA_*`), `electron-builder.yml`,
`electron/package.json` (`build:ollama` and the `dist` chain),
`.github/workflows/release-local.yml`, `modules/llm/router.py`,
`modules/llm/resolution.py`, `modules/llm/selection.py`, `modules/chat/errors.py`.

**Two files in `modules/llm/profile/` are Ollama-shaped and neither appears in
any phase's file list.** `classify.py` is covered by the **Decisions** table
(*Prompt tier fallback* — key on loopback, not on a provider name) but is not
listed anywhere as work. `fingerprint.py` is not covered at all:
`from_ollama(name, tag, show)` is built from `/api/tags` and `/api/show`, and it
needs a `from_llamacpp()` reading `GET /models` and `GET /props` instead. Both
land here.

**Frontend:** `selected-roles.tsx` (`llamacpp` → "Local"; a loopback connection
is arguably also "Local"), `chat-error-notice.tsx`. **Keep**
`connection-form.tsx`'s Ollama preset.

**Egress:** `ollama_pull → registry.ollama.ai` becomes two destinations against
`huggingface.co` — `model_download` (a repo you named) and `model_search` (text
you typed). Same host, different consent. `ollama_pull_host()`'s `hf.co/`
special-case disappears, and with both destinations now static the dynamic
host-resolution path goes with it.

> **The migration maps an existing grant to `model_download` only.**
> `model_search` starts unset. This is the one place "same host, different
> consent" has to be honoured rather than restated: a user who allowed model
> downloads allowed *fetching a file they named*, and search sends text they are
> typing to the same host for a different reason. Splitting one destination into
> two and carrying the grant across both would manufacture consent nobody gave,
> which is precisely the distinction the split exists to draw. The asymmetry is
> safe in the other direction: an unset `model_search` degrades to the airgapped
> product, which **Failure behavior** already specifies.

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
an `ollama_pull` egress row, asserting the grant lands on `model_download` and
that `model_search` is **not** created.

> **`test_ollama_num_ctx.py` is deleted here and its subject is not.** Those two
> tests assert that a full Studio grounding gets a window large enough to hold
> it, which is a real regression guard: Ollama's 4096 default silently dropped a
> 24k-character grounding to a third of its length, measured. llama.cpp fixes
> context at load, so `num_ctx()` has no successor, but the behaviour does. The
> replacement belongs in 7.2, against the context floor: assert the 16K floor
> covers `HISTORY_BUDGET_TOKENS` plus `build_context`'s grounding budget plus a
> reply, so the floor is checked against its stated derivation rather than
> asserted as a constant. Write it before deleting the old one.

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
- **Quantized KV without working flash attention: assert, do not assume.**
  `q8_0` cache requires flash attention, and when the fused kernel is
  unavailable llama.cpp falls back to CPU attention **silently** — no warning,
  the device sits near 0% utilisation and throughput collapses. Two known
  triggers: asymmetric `-ctk`/`-ctv`, and Vulkan on non-NVIDIA hardware, whose
  vendor-neutral `GL_KHR_cooperative_matrix` path was only optimised in mid-2026
  and has an open report of extreme degradation on AMD. So: set both cache types
  identically, verify flash attention engaged after load, and fall back to `f16`
  — accepting the memory cost — rather than running at CPU-attention speed.
  **This is the third silent-degradation case in this phase**, after the probe's
  backend search path (7.2) and a missing backend dependency below. The pattern
  is constant: llama.cpp degrades quietly and exits 0. Assume nothing worked
  until something says it did.
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
- **KV precision is chosen, not defaulted**: a profile where `f16` fits selects
  `f16`; one where only `q8_0` fits selects `q8_0` and records why; one where
  neither fits is `PARTIAL` or `TOO_BIG` as the sizes dictate.
- **`-ctk` and `-ctv` are always equal** in any launch argument set the provider
  builds — asserted on the spawned command line, since a mismatch silently
  disables the fused kernel.
- **The two subtractions stay on their own sides.** A profile where
  `weights + KV + compute ≤ device_free` but `> device_free − fit_reserve`
  asserts **`PARTIAL`**, not `FITS` — the real RTX 3050 case, and the one a
  single collapsed `overhead` term gets backwards.
- **An unmeasured `(platform, backend)` row rounds up.** A budget for a platform
  with no measured reserve never yields a *more* optimistic verdict than the
  measured Windows row on equivalent memory.
- `compute_buffers` is part of `need`: removing the term flips at least one
  fixture from `PARTIAL` to `FITS`, which is the regression to catch.
- Fit states: each of `FITS` / `PARTIAL` / `TOO_BIG` at its boundary, ±1 byte;
  `TOO_BIG` evaluated at the 16K floor, not the requested window; `PARTIAL`
  reachable on a `uma` budget (the Hermes divergence — a regression here silently
  refuses Qwen3 8B on an 8 GB Mac); `PARTIAL` unreachable with no GPU device;
  `can_install` true for `PARTIAL` and false only for `TOO_BIG`; copy resolves to
  the right platform wording for all three budget shapes.
- Recommendation policy: the six hardware profiles above, asserting both pick
  and reason key; and that a searched row is never eligible to be the pick.
- **A `PARTIAL` pair below `MAX_OFFLOAD` is starrable.** The regression fixture
  is the measured RTX 3050: a higher-ranked model at `f ≈ 0.28` beats a fully
  resident lower-ranked one. A `FITS`-only policy fails this test, which is the
  point of having it.
- **`offload_fraction` survives to the verdict** and is not recomputed by the
  renderer; the graded reason line is selected from it, and the same fraction
  drives both the gate and the copy.
- `TOO_BIG` is still refused regardless of rank: the ceiling relaxes residency,
  never physics.
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

**Offload sweep**, Qwen3 4B Q4_K_M, `-ngl` controlling `f` directly, f16 KV,
`-p 512 -n 300`, Vulkan, RTX 3050:

| ngl | `f` | pp512 | tg300 |
|---|---|---|---|
| 99 | 0.00 | 1805.50 ± 1.75 | 52.45 ± 0.17 |
| 28 | 0.22 | 1454.68 ± 0.93 | 33.17 ± 0.25 |
| 18 | 0.50 | 1206.29 ± 9.86 | 19.85 ± 1.06 |
| 9 | 0.75 | 1027.97 ± 26.10 | 12.93 ± 0.43 |
| 0 | 1.00 | 907.43 ± 26.49 | 13.13 ± 0.67 |

`ngl 0` edging out `ngl 9` is real: splitting across devices costs transfers that
outweigh nine layers of device work.

**KV precision.** Resident, depth 0: `f16` pp8192 1437.66 / tg300 52.47 against
`q8_0` 1300.44 / 51.34.

> **That comparison is at the wrong depth and should not be quoted as q8_0's
> cost.** At depth 0 the cache is nearly empty, so its precision cannot matter;
> published CUDA figures showing ~18% at 8K depth were measured under different
> conditions. The valid comparison — `f16` at 16K depth — **could not be taken**,
> because it fails to allocate on this card. What is known: `q8_0` at depth 16384
> decodes at 27.46 t/s against 51.34 at depth 0, and that halving is the cost of
> attending over a long context, not of quantizing it. **q8_0's real cost at
> depth on Vulkan is unmeasured**; it needs a card with enough VRAM to run `f16`
> at 16K.

**The decisive result.** `f16` KV at a 16K window on a 6 GB card:

```text
ggml_vulkan: Device memory allocation of size 316407808 failed.
ggml_vulkan: vk::Device::allocateMemory: ErrorOutOfDeviceMemory
llama_bench: error: failed to create context
```

`q8_0` at the same depth runs. On this class of card the planned configuration
does not fit, which is what makes KV precision a fit-calculation output rather
than a default.

**Fit terms, measured.** Qwen3 4B Q4_K_M at `-c 16384`, `--fit` on, RTX 3050
with 5,234 MiB free, from llama.cpp's own allocation log:

| buffer | MiB |
|---|---|
| `Vulkan0` model | 2078.04 |
| `CPU_Mapped` model (spilled) | 602.16 |
| `Vulkan0` KV | 1984.00 |
| `CPU` KV (spilled) | 320.00 |
| `Vulkan0` compute | 143.62 |
| `Vulkan_Host` compute | 26.01 |
| `Vulkan_Host` output | 2.32 |
| **placed on device** | **4205.66** |
| **fit reserve (unused)** | **1028.34** |

**The KV formula is exact, not approximate.**
`2 × 36 layers × 8 kv_heads × 128 × 2 bytes × 16384` = **2304 MiB**, against
`1984 + 320` measured. Qwen3 0.6B independently: predicted `378 + 1792 + ~60` =
2,234 MiB, measured VRAM delta **2,234 MiB**. That is the evidence that a curated
row can be priced offline from committed `shape` fields alone.

**Apple Silicon, measured on an M2 / 8 GB at `b11050`.** The platform the
reserve table listed as unmeasured. Qwen3 1.7B Q4_K_M, `llama-server -v`.

| Measurement | Value |
|---|---|
| `ggml_backend_load_all()` | **2.3 ms** |
| first `ggml_backend_dev_count()` (compiles 20 Metal libraries) | **19.0 s** cold, 43 to 49 ms warm |
| `ggml_backend_dev_memory()` | 0.02 ms |
| devices listed | `MTL0` (GPU), `BLAS` (ACCEL, raw type 3), `CPU` |
| `recommendedMaxWorkingSetSize` | 5726.63 MB = **5461.3 MiB**, which is what ggml reports as MTL0 total |
| MTL0 total / free | 5461.3 / 5461.0 MiB — **not a live figure** |
| CPU device total / free | 8192.0 / 8192.0 MiB — physical RAM, twice, on a machine with ~2 GB free |
| fit margin the fitter names | **1024 MiB** |

At `-c 16384`, `--parallel 1` would have been the right flag and was not passed;
llama-server defaults to **4 slots**, so pass `--parallel 1` or the KV cache is
sized for concurrency this app does not use.

| buffer, `-c 16384` | MiB |
|---|---|
| `MTL0_Mapped` model | 1050.43 |
| `CPU_Mapped` model | 243.43 |
| `MTL0` KV | 1792.00 |
| `MTL0` compute | 102.24 |
| `CPU` compute | 24.01 |
| `CPU` output | 2.32 |
| **fitter's own projection** | **2944** |

`1050 + 1792 + 102 = 2944`, against the fitter's `projected to use 2944 MiB`.
**The three-term `need` is exact on Metal**, as it was on Vulkan.

**The KV formula is exact on Metal too.** `2 × 28 layers × 8 kv_heads × 128 ×
2 bytes × 16384` = **1792 MiB**, reported as `1792.00`. At 40,960 cells it is
`4480.00`, again exact. Compute buffers scale with context as stated: 102.24 MiB
at 16K, 222.24 MiB at 40K.

**243.43 MiB stayed on the CPU at "offloaded 29/29 layers to GPU".** The
non-repeating tensors are host-side even at full offload, so *29/29 offloaded*
does not mean *all weights on the device*, and an `offload_fraction` derived from
the layer count alone will read 0.00 when 19% of the file is elsewhere.

**Metal reports `0.00 MiB` buffer sizes during the fitter's probe pass**, before
the real load. Anything scraping buffer sizes must ignore the first pass, and
`use shared buffers = true` means Metal allocations are not the separate arenas
Vulkan and CUDA report.

**`--fit` searches rather than solves.** At `-c 40960`, needing 5752 MiB against
5460 free with a 1024 margin: `29/29 → 0/29 → 29/29 → 22/29 → 23/29`, reloading
at each step, settling at 23/29 (`f ≈ 0.21`). It never reduced the context,
because `-c` was explicit.

**Router lifecycle.** Router up with three models discovered: VRAM unchanged from
idle. Worker spawn: `--port 0 --model <path>`. Idle eviction ~30 s without
`--sleep-idle-seconds`. Grandchild reaping via `taskkill /T /F`: four processes,
depth first, no survivors.

**`-ngl` disables `--fit`.** With `-ngl 99`: `common_fit_params: failed to fit
params to free device memory: n_gpu_layers already set by user to 99, abort`,
after which the model loaded entirely on CPU with 478 MiB of VRAM touched, no
error, exit 0.

**`POST /models/load` ignored `{"args": ["-c","16384"]}`** — workers came up at
`n_ctx_slot` 34304 / 28160 / 12288 (model defaults). The same flag on the
`llama-server` command line **is** honoured (`n_ctx_slot = 16384`). See 7.3.

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
