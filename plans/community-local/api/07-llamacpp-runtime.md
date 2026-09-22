# API — Phase 7: the llama.cpp runtime

> **Status: built.** This document describes what is implemented on
> `feat/llama-cpp`, and the reasoning behind each decision, so a reader can
> change the code without rediscovering why it is shaped this way.
>
> Owns `modules/llm/` (providers, fit, gguf, hardware, catalog), the
> `llama-server` sidecar, the curated manifest, and packaging for all three
> targets. Supersedes the Ollama runtime decision in
> [`../00-umbrella-plan.md`](../00-umbrella-plan.md), the `hf.co/` fallback in
> [`05d-llmfit-catalog-expansion.md`](05d-llmfit-catalog-expansion.md), and the
> recommendation half of
> [`05a-model-recommendations.md`](05a-model-recommendations.md), which is
> reduced to prompt tiers, fingerprinting and onboarding.
>
> Ollama and llmfit are gone from the product. Ingestion, the 384-dimensional
> bge-small index, retrieval, Kokoro, local image generation and the chat SSE
> protocol are unchanged.

## Goal

One local runtime: `llama-server` in router mode. Any GGUF model the user wants,
not a curated subset. A fit verdict that comes from the allocator's own view of
the machine rather than from an advisor's database.

## Why llama.cpp replaced Ollama

Ollama's library held 240 models. A measured scan on this branch resolved 138 of
9,590 llmfit rows to an installable Ollama artifact, 1.4%. The `ollama_name`
gate in `OllamaRuntime.resolve()` dropped every model Ollama's registry did not
carry, including roughly 1,500 per scan that llama.cpp could run directly from a
Hugging Face GGUF.

llama.cpp runs anything in GGUF: 204,797 repos on Hugging Face, bounded only by
the architectures it supports. It also ships smaller (11 to 31 MB against
Ollama's 501 MB staged payload), fits models to the machine itself (`--fit`,
default on), and exposes multimodal and structured-output contracts Ollama's
native API did not.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| **Runtime** | `llama-server` router mode, one sidecar | `--models-dir`, `--models-max 1`, one PID for the supervisor to reap, and a process that costs no device memory until a model loads. |
| **Per-model flags** | A preset INI, read once at router startup | `POST /models/load` accepts an `args` field and ignores it, measured. `--models-preset` is the mechanism that works. |
| **Layer placement** | `--fit` owns it. We never set `n-gpu-layers` | Setting it by hand aborts the fitter, after which the model loads entirely on the CPU with exit 0 and no error. |
| **GPU backend** | Vulkan on every platform off Apple Silicon. No CUDA payload | Measured on an RTX 3050 at `b11050`: CUDA leads Vulkan 9.1% on `pp512`, 10.2% on `pp8192`, 2.1% on decode. That is 0.66 s on an 11 s turn, for 685 MB. Vulkan covers NVIDIA, AMD and Intel from one 31 MB archive and its loader ships with Windows. CUDA is specified as an optional later addition in [`08-cuda-backend.md`](08-cuda-backend.md) and needs no code change, because ggml selects a backend by the files present. |
| **MLX** | Not shipped. Revisit after launch | MLX's format covers 23,985 HF repos against GGUF's 204,797. One format and the full catalog wins. Mac users who want MLX point a connection at LM Studio; see **The Mac path**. |
| **llmfit** | Authoring-time only. Not shipped, not in CI, not in any request path | A person runs `scripts/refresh_curated_models.py` when adding or changing a curated entry, a few times a year, and commits the numbers. |
| **Install gate** | One denylist, keyed by both the GGUF architecture and the repo's pipeline tag | A denylist ages the right way: llama.cpp gains architectures every few weeks, so an unknown name is usually a chat model released last week. The allowlist this replaces was generated from the pinned `libllama` and was correct, but it cost a script run per pin bump and a data file that had to ship because the symbol it reads is not exported on Windows. Measured over the 1000 most downloaded GGUF repos, dropping it lets 18 of 979 install and then fail, all of them architectures released in the last few weeks. Accepted: curated is the default path, search is opt in, and `MODEL_CANNOT_RUN` now says the model will not run rather than asking the reader to retry. |
| **GGUF parser** | llama.cpp's own `gguf` package, pinned at `0.19.0` | The search tier parses bytes from arbitrary repositories, and upstream's parser is the one that receives hardening. A 150-line adapter handles the one thing it cannot do, which is read a header out of a byte prefix. |
| **Hardware budget** | `ggml_backend_dev_memory()` through `ctypes`, in a child process | The allocator's own view. The child exists because the backend scan keys on the running executable's directory, because a driver fault would otherwise take the API with it, and because the first Metal device query compiles 20 shader libraries in 19 seconds. |
| **Device selection** | First device typed `GPU`. Never a sum | The same physical card appears once per loaded backend, and an integrated GPU can advertise more memory than a discrete one, 16198 MiB against 6002 MiB measured. ggml already orders backends by preference, so taking the first is also backend selection. |
| **Two memory questions** | `resident_bytes` and `refusal_bytes`, never one `overhead` term | They sit on opposite sides of the comparison. Collapsing them predicted residency for a configuration that measurably spilled, wrong by 922 MiB on the first attempt. |
| **Unified memory** | One pool: `min(working set, 0.85 x host)`. Never a sum | Apple Silicon reports two views of one memory. Added together, an 8 GB Mac priced as though it had 10.3 GB. |
| **Gating** | Only physics refuses | `can_install` is `state is not TOO_BIG`. `PARTIAL` installs exactly like `FITS`. Eligibility (architecture, chat template, gated repo) blocks separately and is not a fit state. |
| **Context** | Fixed at load. Floor 8192, rungs 8192 / 16384 / 32768, capped at the model's own `context_length` | llama.cpp fixes context at load, so per-request sizing has no equivalent. The floor is safe because `modules/chat/budget` sizes every part of a prompt from `n_ctx` rather than from a fixed history figure. |
| **KV precision** | `f16` when it fits, `q8_0` only when it converts a spill into residency | Measured: `f16` KV at a 16K window cannot allocate on a 6 GB card (`ErrorOutOfDeviceMemory`) while `q8_0` at the same depth runs. Quality is identical either way, but a quantized cache needs a working flash-attention kernel and `f16` does not, so the dependency is taken only where it pays. One rule, in `fit/precision.py`, read by the badge and by the loader. |
| **Catalog** | Two tiers: a curated manifest and Hugging Face search | Curated is the offline product and ships frozen. Search is a network feature and is simply absent airgapped. |
| **Fit badge** | Every row, both tiers | Fit is subtraction, not judgement. Exact from committed `shape` for curated, exact from the header for an opened search result, approximate from file size when a header cannot be read. |
| **`rank`** | Curated entries only, inside the variant, never on the wire | A preference order over models we tested for this app's job, answering from documents with citations that resolve. It is only ever a sort key, so it must not imply a measurement we do not have. A searched model never carries one. |
| **Recommendation** | Highest `rank` among builds whose speed tier is recommendable | Residency is a mechanism and speed is the goal, and on small cards they disagree. Both the badge's wording and the star's eligibility read one classification, so they cannot contradict each other. |
| **Downloads** | SurfSense fetches the GGUF, not `POST /models` | `llama-server` is a second process we do not proxy, so an in-process fetch is the only place `egress.require()` can hold. It also buys resume, checksums, and the header as the file lands. |
| **Install ids** | Opaque, server-minted, for both tiers | The renderer sends a `catalog_id` and nothing else. Letting it post a repo and file would hand the frontend the ability to name an arbitrary download. |
| **Egress** | `model_download` and `model_search`, both `huggingface.co` | Same host, different consent. A user who allowed model downloads allowed fetching a file they named; search sends text they are typing. |
| **Prompt tier fallback** | Keys on loopback, not on a provider name | `provider == "ollama"` broke the moment a Mac user ran a 4B through LM Studio. `host_destination()` already computes loopback. |

## Boundaries

```text
  hardware ──── probe_devices()  child process, ggml's own device list
      │              │
      │              └─ gpu_status: present | absent | broken_install | unknown
      │
  budget ────── build_budget(devices, ram)   one device, never a sum
      │              resident_bytes   what must hold the model for full speed
      │              refusal_bytes    what physics allows at all
      │
  model ─────── GGUF header, local file or HTTP Range on huggingface.co
      │              ModelShape: 19 fields, quantization independent
      ▼
  estimate ──── itemise() -> weights + mmproj + KV(window) + compute
      │         FITS | PARTIAL | TOO_BIG, plus an offload fraction in layers
      │              │
      │              └─ speed_tier() ─┬─ copy.badge()      what the row says
      │                               └─ RECOMMENDABLE_TIERS   whether it stars
      ▼
  CatalogService ── curated (manifest, offline) + search (HF, egress gated)
      │              plan_load() -> window and cache precision
      │              reprice()  -> models.ini
      ▼
  llama-server router ── --fit places the layers. That is the real answer.
```

The estimate is advisory at every stage above the runtime. `--fit`'s allocation
is authoritative at load, and generation is ground truth after that. Unknown
shapes round up; never underestimate memory. An over-estimate costs a
pessimistic badge on a model that installs anyway. An under-estimate ships a
confident badge about a model that spills, which is the failure this estimator
exists to delete.

## The Mac path

Dropping Ollama costs Apple Silicon speed on models under roughly 14B. Accepted,
because the escape hatch already ships and does not leave the machine:

- `host_destination()` returns `None` for loopback, so `require()` no-ops and no
  egress prompt appears.
- `api_key_ciphertext` is nullable and `_headers(None)` returns `{}`, so keyless
  local endpoints work end to end.
- `connection-form.tsx` ships `LM Studio (local)` and `Ollama (local)` presets.

LM Studio runs MLX on Apple Silicon. A Mac user who wants it installs LM Studio
and picks the preset. **The Ollama preset is kept deliberately**: it is the
user-managed MLX path now, not dead code, and it is one of the few places the
string `ollama` legitimately survives.

## The runtime

### Router mode, and why the preset file exists

`llama-server` starts in one of two shapes. Given `-m <path>` it loads that one
model and serves it. Given `--models-dir <dir>` and no `-m` it starts as a
**router**: it holds no model, lists every GGUF in the directory as `unloaded`,
and spawns a child worker per model when one is loaded. `GET /props` reporting
`"role": "router"` is the check that the sidecar came up the way we asked; both
shapes answer `/health` identically.

Router mode is what lets the sidecar boot before any model is installed, which
matters on a clean machine where the models directory is empty. Verified at
`b11050` on Windows and Linux: `/health` returns `{"status":"ok"}` and `/models`
returns `{"data":[],"object":"list"}` against an empty directory.

The cost is that per-model arguments cannot be sent at load time. Measured on
macOS at `b11050`, every payload shape is accepted and none of them does
anything: `{"args": ["-c","4096"]}`, `{"args": ["--ctx-size","4096","-fa","on"]}`
and `{"preset": "..."}` all return `200 {"success":true}` while the spawned
worker's argv stays byte identical. The router reports that argv under
`GET /models` as `status.args`, which is the only reliable way to see what it
actually did.

`--models-preset PATH` is the mechanism that works, and **the file is read once
at router startup**. Appending a section while the router runs does not surface
the model. Measured: a model dropped into a running router's directory is still
invisible 26 seconds later and appears immediately after a restart. So
installing a model, or changing its load plan, means rewriting the file and
restarting the sidecar, which costs 0.15 s because an idle router holds no model
memory.

### Sidecar flags

From `electron/src/main/sidecars/llamacpp.ts`:

```text
--models-dir <dataDir>/models
--host 127.0.0.1  --port <free>
--models-max 1
--sleep-idle-seconds 300
--no-ui
--jinja
--reasoning-format deepseek
--models-preset <dataDir>/models/models.ini      (only once the file exists)
```

with `cwd` set to the binaries directory and `LLAMA_CACHE` pointed at the models
directory.

- `--models-max 1` because this app asks one question at a time, and a second
  resident model is memory taken from the one being used.
- `--sleep-idle-seconds 300` is not optional. Measured at `b11050`, a model
  without it self-evicted after roughly 30 s idle, which turns the second
  question of a conversation into a reload.
- `--no-ui` because llama-server ships its own web UI, which we neither need nor
  want exposed.
- `--reasoning-format deepseek` routes `<think>` blocks to
  `message.reasoning_content`. Without it a thinking model's trace enters the
  answer and citation rewriting corrupts `[n]` tokens that appeared inside the
  reasoning.
- `cwd` is the binaries directory because ggml scans the running executable's own
  directory for backend libraries. Elsewhere it reports no devices, silently,
  and every model runs on the CPU.
- The preset flag is conditional because the router exits non-zero on a missing
  preset file, and on a clean install nothing has written one yet.

`watchGenerationPreset()` in `electron/src/main/index.ts` polls the preset's size
and mtime every 5 s and restarts the sidecar on a change. Same shape as
`watchImageModel()` for sd-server, and for the same reason: the API is the
authority, and a change is user-initiated and rare.

### Never set a layer count

```text
common_fit_params: failed to fit params to free device memory:
                   n_gpu_layers already set by user to 99, abort
```

Measured at `b11050`: with `-ngl 99` the model then loaded **entirely on the
CPU**, 478 MiB of VRAM touched on a machine with a working RTX 3050, no error,
exit 0. It looks like it worked.

This is the easiest silent failure in the phase to introduce by accident, since
`-ngl 99` reads as "use the GPU harder". The preset therefore writes no layer
count at any time, and `preset.py`'s docstring says so where someone would go to
add one.

What `--fit` does instead, measured at `-c 40960` against a 5,460 MiB working
set, is search rather than solve, reloading at each step:

```text
29/29 layers → 0/29 → 29/29 → 22/29 → 23/29      settles at 23/29
```

Two behaviours matter. It never touched the context, because `-c` was set
explicitly and the fitter treats an explicit value as fixed. And if `-c` is left
unset it reduces context on its own as far as `fit_params_min_ctx`, 4096, which
is below our floor and happens silently. So `ctx-size` is not optional, and not
only because we want a particular window: leaving it out hands the floor to
llama.cpp.

### The preset file

`modules/llm/providers/llamacpp/preset.py` renders one section per model, keyed
by the id the router reports, which is the filename stem:

```ini
[Qwen3-8B-Q4_K_M]
model = /Users/…/models/Qwen3-8B-Q4_K_M.gguf
ctx-size = 16384
parallel = 1
fit-target = 1024
fit-ctx = 16384
mmproj = /Users/…/models/mmproj-F16.gguf       ; only with a projector
cache-type-k = q8_0                            ; only at q8_0
cache-type-v = q8_0
flash-attn = on
```

- `parallel = 1`. llama-server defaults to four slots, which sizes the KV cache
  for concurrency this app never uses.
- `fit-target` is pinned rather than inherited. The badge subtracted a specific
  margin, so passing it makes the two agree by construction instead of by
  assuming a default read from the source once. A vision projector's bytes are
  **added** to it, because `--fit` allocates the projector after it has finished
  placing layers and does not count it while deciding
  ([llama.cpp#19980](https://github.com/ggml-org/llama.cpp/issues/19980)).
- `fit-ctx` is inert while `ctx-size` is set, since llama.cpp only shrinks a
  context it chose itself. It is written anyway because it states the floor at
  the place the fitter would look for one, so a later change to how the window is
  set cannot quietly hand that floor back to llama.cpp's 4096.
- The `q8_0` lines are written as a group. Set one cache type and not the other
  and the fused flash-attention kernel is skipped, after which attention falls
  back to the CPU silently.

`write_presets()` writes to a sibling `.tmp` and renames, so a half-written INI
never loads.

### From download to answerable

`CatalogService.reprice()` writes the preset for everything now on disk, priced
against two budgets: capacity decides the verdict so the plan agrees with the
badge the catalog already showed, and live caps how far the window widens past
the floor, because that part is opportunistic and on unified memory it comes out
of the same pool the OS is using.

It skips projector files, because a projector is half of a vision model and has a
header and a size like any other file in the directory. It skips unreadable files
with a warning, because a truncated or foreign file costs that one model, while
failing would leave the runtime dead over a file nobody asked it to load.

The install stream then waits: `wait_until_servable()` polls for up to 30 s at
0.5 s intervals, because the router only learns about a new model by restarting,
and reporting the install complete before then tells the user a model is ready
while a chat returns `model '<id>' not found`, measured as a 400. A timeout
returns `False` rather than raising. The download did succeed and the file is on
disk, so reporting a failed install would be the wrong thing to say.

### Turning thinking off

A thinking model emits its whole trace before its first answer token, so a call
with a small `max_tokens` returns nothing. Measured against Qwen3 1.7B at
`b11050`: a 12-token title request came back with `content: ''`,
`finish_reason: length`, and a full `reasoning_content`.

`thinking.py` sends two mechanisms per call, because each covers the other's
blind spot and both were measured to work:

```python
THINKING_OFF = {
    "thinking_budget_tokens": 0,
    "chat_template_kwargs": {"enable_thinking": False},
}
```

`chat_template_kwargs` is the documented one and is inert on a model whose
template never reads `enable_thinking`. `thinking_budget_tokens` is llama.cpp's
own end-of-thinking injection, so it holds whatever the template does.

Two rejected alternatives, both measured. `reasoning_budget` as a request field
is accepted and ignored, which is the failure mode worth naming because it looks
like it worked. `--reasoning-budget 0` on the command line applies to the whole
router, and worse, setting it at all makes the server ignore
`thinking_budget_tokens`, whose handler runs only while the flag is at its `-1`
default. The sidecar must never pass it, and a test in the Electron tree holds
that.

### The provider

`LlamaCppProvider` satisfies the same `Generator` protocol the previous runtime
did, so resolution, selection and the catalog never learned that the runtime
changed.

| Ollama call | llama-server |
|---|---|
| `GET /` | `GET /health` |
| `GET /api/tags` | `GET /models`, plus `architecture.input_modalities` |
| `POST /api/show` | `GET /props?model=…`: `chat_template_caps`, `n_ctx` |
| `POST /api/pull` | we fetch `resolve/main/{file}` ourselves |
| blob cleanup on cancel | deleted, about 40 lines |
| `DELETE /api/delete` | unlink the file ourselves |
| `POST /api/chat` | `POST /v1/chat/completions` |
| nothing equivalent | `POST /tokenize` |

Three of those deserve their reasoning written down.

**Chat is composed, not reimplemented.** llama-server speaks OpenAI on
`/v1/chat/completions`, so the streaming, error handling and message shaping in
`OpenAICompatibleChatProvider` work against it unchanged. The one addition is a
fallback: [llama.cpp#29006](https://github.com/ggml-org/llama.cpp/issues/29006)
returns 400 for `json_schema` on some templates, and losing a whole Studio format
to a template quirk is worse than falling back to an unconstrained answer the
parser can still repair.

**There is no `pull()`, deliberately.** Fetching weights from a name made sense
when the runtime owned the download. Here SurfSense fetches the GGUF itself,
because that is the only place `egress.require()` can hold.

**Delete unlinks the file rather than calling `DELETE /models`.** The router only
removes what it downloaded into its own cache and refuses everything else:
measured, `model name=… is not removable (not from cache)`, a 500, with the file
left on disk. Everything SurfSense installs lands in `--models-dir`, so that call
can never succeed for us.

`/props` is read once per load rather than once per message, cached by model id
and cleared only by `_ensure_loaded()` issuing a fresh load, which is the one
event that can make the old answer wrong. Before that cache, `context_tokens()`
and `chat()`'s own template shaping each issued an independent round trip on
every turn.

## Reading a model

### The parser

`gguf==0.19.0`, llama.cpp's own `gguf-py` package, pinned exactly rather than
ranged. Two reasons it is upstream's parser and not one of ours: the search tier
parses bytes from arbitrary Hugging Face repositories, which is the one path
where a malformed file is adversarial rather than unlucky; and metadata key names
come from `gguf.constants.Keys`, so a rename upstream is an import error rather
than a field that silently reads zero.

`scripts/curated/tensor_bytes.py` takes the same view for sizes and tensor names,
reading `GGML_QUANT_SIZES` and `TENSOR_NAMES` rather than restating either.

### Reading a header out of a prefix

`GGUFReader` memory-maps a **path** and its constructor always walks the tensor
table, slicing each tensor's data at an offset inside the weights. A prefix has
no weights, and numpy shortens a slice that runs past the end rather than
raising, so the shortfall would surface later as a confident wrong shape instead
of a retry.

`modules/llm/gguf/header_prefix.py` is the adapter, and it overrides exactly two
private methods:

- `_get` bounds-checks every read and raises `TruncatedHeaderError` when the
  prefix is short.
- `_build_tensors` keeps names, dimensions and raw type ids without touching
  data.

`TruncatedHeaderError` subclasses `ValueError` on purpose. A caller that can
widen the read catches it by name and retries; a caller that merely needs to skip
an unusable file catches `ValueError` and gets both this and a file that was
never a GGUF.

Because both methods are private upstream, the version is pinned exactly and
`test_header_prefix.py` asserts `gguf.__version__` beside the two behaviours, so
a bump cannot pass silently.

The reader also closes its memory map explicitly. Windows refuses to unlink a
mapped file, and this runs once per searched model.

### Where header bytes come from

`modules/llm/gguf/source.py`. Hugging Face serves `Range` requests on model
files, so a model can be priced before a single weight is downloaded, which is
what puts a real fit badge on a search result. Verified: HF returns `206` with
`accept-ranges: bytes`.

The widening is the point of the module. A 135M model's metadata ends at 1.77 MB;
Qwen3-Coder-30B-A3B's runs to 5.94 MB with 579 tensor entries after it. Header
size scales with **vocabulary**, not with model size, so no single prefix suits
every model:

```python
INITIAL_BYTES = 8 * 1024 * 1024
WIDENED_BYTES = 24 * 1024 * 1024
```

A short read is a retry, once, and then a refusal.

### `ModelShape`

Nineteen fields, named after the GGUF metadata keys they come from.
Quantization-independent: measured, the architecture fields are identical across
`Q4_K_M`, `Q8_0` and `f16` of the same model, so **one header read prices every
build of it**. Seven are required; the rest default to zero, and each one only
ever makes an estimate sharper, with absence being the conservative answer rather
than a zero cost.

| Group | Fields |
|---|---|
| Required | `architecture`, `block_count`, `head_count_kv`, `key_length`, `value_length`, `context_length`, `n_vocab` |
| Graph width | `embedding_length`, `feed_forward_length`, `expert_feed_forward_length`, `expert_shared_feed_forward_length`, `expert_used_count`, `expert_count` |
| Sliding window | `sliding_window`, `sliding_window_pattern`, `sliding_window_layers`, `shared_kv_layers` |
| Latent attention | `kv_lora_rank`, `key_length_mla` |

Two reading rules in `shape.py` are worth knowing. A field that is scalar in most
models and per-layer in some is reduced with `_widest()`, because the widest
layer is what the cache must be sized for and taking the first element would
under-price a hybrid. And older headers that omit the per-head lengths have them
implied from `embedding_length // head_count`.

## Reading the machine

### The probe runs out of process

`probe_subprocess.probe_devices()` spawns a child, and the in-process path
survives only as a fallback. Three measured reasons, each independently
sufficient:

**The backend scan keys on the running executable's directory.**
`ggml_backend_load_all()` discovers backends by scanning the directory of the
running executable, not the directory the libraries were loaded from. Verified on
a Windows machine with a working RTX 3050, same minute, same process otherwise:

```text
python wprobe.py                      →  device count 0     card invisible
cd <llamacpp dir> && python wprobe.py →  device count 2     Vulkan0 + CPU
```

Loading the libraries by absolute path does not help, and `GGML_BACKEND_PATH` is
not an escape hatch because it expects a file: passing a directory logs
`load_backend: failed to load <dir>` and leaves the count at zero. In process
this meant a process-global `chdir` under a lock, inside a server that is
handling other requests. In a child it is just the working directory.

**The first Metal device query compiles 20 shader libraries.** Measured on an M2:
`ggml_backend_load_all()` is 2.3 ms, and the compile happens inside the first
`ggml_backend_dev_count()`, at 19.0 s cold and 43 to 49 ms warm. A background
warm that calls `load_all()` and stops therefore warms nothing. The warm has to
enumerate the devices, which is what `CatalogService.warm()` does on a daemon
thread at lifespan start, so `/health` answers within a second of boot.

**A GPU driver that faults takes its process with it.** A child is a probe that
failed. The API process is the application.

The child protocol is one tab-separated line per device on stdout:

```text
name<TAB>description<TAB>type_int<TAB>total_bytes<TAB>free_bytes
Vulkan0	NVIDIA GeForce RTX 3050	1	6293553152	5487271936
```

Deliberately plain, because ggml logs to stdout on some backends and the child's
output is shared with whatever it decides to print on the way past. A line that
does not parse is skipped rather than taking the listing with it, since it is far
more likely to be a log line than a device. A non-zero exit or a timeout (90 s,
bounding the Metal compile) logs a warning and falls back in process.

The frozen binary re-executes itself behind `--probe-devices`, dispatched in
`main.py` beside the existing `--check-retrieval-runtime`. In development the
child is `python -m modules.llm.hardware.probe_script` with the backend root on
`PYTHONPATH`. The library directory is resolved before it is handed over, because
the child is started *in* that directory and a relative path would be read again
against it, find nothing, and fall back in process: the exact behaviour the
module exists to avoid, and silent, because the fallback answers.

### Two library handles on Windows, one elsewhere

The exported symbols are split, and the intuitive single handle fails:

| Library | Exports |
|---|---|
| `ggml.dll` / `libggml.so` / `libggml.dylib` | `ggml_backend_load_all`, `dev_count`, `dev_get` |
| `ggml-base.*` | `dev_name`, `dev_description`, `dev_type`, `dev_memory` |

ELF and Mach-O resolve the second through their own dependency records, so one
`CDLL("libggml.so")` works, while `CDLL("libggml-base.so")` raises `undefined
symbol: ggml_backend_load_all`. **Windows needs both handles**: PE exports do not
chain, and `ggml.dll` alone raises `AttributeError: function
'ggml_backend_dev_name' not found`. A regression here is an `AttributeError` at
startup rather than a wrong answer, which is why it carries an explicit test.

### Device selection

A machine reports one entry per (backend, device) pair. Measured on the Windows
test machine:

```text
[0] Vulkan0  type=GPU    6002.0 MiB total, 5234.0 MiB free   NVIDIA GeForce RTX 3050
[1] Vulkan1  type=ACCEL 16198.3 MiB total                    AMD Radeon(TM) Graphics
[2] CPU      type=CPU   31884.6 MiB total, 22750.2 MiB free  AMD Ryzen 5 9600X
```

`select_device()` takes the first device typed `GPU`, or `None`.

- **First, not largest.** Sorting by memory picks the 16 GB integrated part over
  the 6 GB discrete card and places every layer on the slower device.
- **Never a sum.** One device becomes the budget. The same card appearing twice
  under two backends would otherwise turn a 6 GB card into 12 GB.
- **An integrated GPU is not a GPU for budgeting.** A part carving from system
  RAM has no memory of its own to place layers in. It types as `IGPU`, and both
  it and `ACCEL` are skipped by the `type is GPU` filter.

`DeviceType` models all five ggml members plus an `UNKNOWN` sentinel, and
`parse()` maps an unrecognised integer to `UNKNOWN` rather than raising. That is
not defensiveness for its own sake: every Mac lists an Accelerate `BLAS` device
at raw type 3, so a three-member enum would raise `ValueError` at first paint on
a perfectly healthy machine. ggml has added a member twice.

### Host memory does not come from ggml

ggml's CPU device reports real available memory on native Windows and, so far,
nowhere else. Under WSL2 the figure is virtualised and `total == free`. On macOS
it is worse: measured on an M2 with roughly 2 GB genuinely free, the CPU device
reports 8192.0 MiB total against 8192.0 MiB free, physical RAM restated twice
with no live component at all.

So `system_memory.available_bytes()` asks the OS. On Linux it parses
`MemAvailable` from `/proc/meminfo`; on macOS it runs `vm_stat` and sums free
plus inactive pages, which is what a large allocation can actually claim; and it
falls back to `sysconf` totals rather than to zero. `Device.reports_live_memory`
exists so a `free == total` reading is treated as "this device does not report
live memory" rather than as an idle machine.

This matters because `ram_available_bytes` is what separates `PARTIAL` from
`TOO_BIG` on a discrete card.

### Unified memory is one pool

Apple Silicon reports two views of one memory: Metal states
`recommendedMaxWorkingSetSize` as both its total and its free, while the host
states the same physical memory again. Summed, an 8 GB Mac priced as though it
had 10.3 GB, and the refusal threshold came out at 10,581 MiB.

```python
UMA_HOST_FRACTION = 0.85

def unified_pool_bytes(working_set_bytes: int, host_bytes: int) -> int:
    return min(working_set_bytes, int(UMA_HOST_FRACTION * host_bytes))
```

Two limits apply and the smaller governs. The working set is a ceiling Metal will
not allocate past, and it is exactly the figure llama.cpp's fitter subtracts its
own margin from, so discounting it again would refuse a model the runtime
demonstrably places. Host memory is what is actually there, and that is the leg
that lies: it is a snapshot, and loading weights takes seconds during which
another application can take memory.

The 0.85 earns that second job. Measured: spending the working set as though it
were live sized a 28,672 token window on an 8 GB Mac with 2.3 GB reclaimable, the
load paged, and it took 43 seconds, long enough for title generation to time out
at 30.

A GPU sharing the CPU's description is the signal that the memory is shared.
Apple Silicon reports the same part name for both, which is cheap and reliable.

### GPU status: four answers, not two

ggml answers an empty device list with exit 0 on two very different machines: a
laptop with no graphics card, and a workstation whose backend library did not
ship. Measured on Windows and Linux with a working card and `ggml-cuda.dll`
staged but no cudart beside it, `--list-devices` prints `(none)` and exits 0, and
`GGML_BACKEND_DEBUG=1` changes nothing.

Badging the second as the first is the failure `gpu_status.py` exists to stop:
the user sees every model marked as running on the processor, with no suggestion
that the card they bought is idle because a file is missing.

| ggml sees a GPU | OS sees a GPU | Status |
|---|---|---|
| yes | either | `present` |
| no | yes | `broken_install` |
| no | no | `absent` |
| no | cannot say, a CPU device was listed | `absent` |
| no | cannot say, nothing was listed | `unknown` |

The OS half is `Win32_VideoController` through PowerShell on Windows,
`card*/device/vendor` under `/sys/class/drm` on Linux, and `True` on arm64 macOS.
Virtual adapters are filtered: the Windows test machine carried a `Parsec Virtual
Display Adapter` beside two real GPUs.

`present` means ggml listed a GPU, which is not the same as the budget being
priced against one. An integrated part counts here and is still skipped by
`select_device`. The two questions are "is the runtime seeing the hardware" and
"what will hold the layers", and conflating them is how an AMD APU laptop would
end up badged as broken.

The diagnosis travels beside the budget rather than inside it, on both
`GET /llm/system` and `GET /llm/catalog`. The budget is memory; this is a
diagnosis; and a broken install must not read as a machine that has no card.

### Two budget modes

The same subtraction answers two different questions.

**Capacity** prices a catalog, which is a shelf of models you might install
later and must not move with whatever the machine happens to be doing right now.
Host memory is `total - 2 GiB`, the reserve a host keeps for itself once a model
is resident.

**Live** decides a launch: this model, into this memory, in a moment.

Pricing the catalog against live free memory makes every large row read
`TOO_BIG` whenever a browser is open, which is a badge that lies in the direction
users notice. The catalog therefore defaults to capacity, and `plan_load` takes
both.

One subtlety worth preserving. The 2 GiB reserve is only meaningful against
physical RAM. When nothing states the total, the live reading is a **floor**
rather than another figure to deduct from. Subtracting twice reported 0 GB on a
busy 8 GB machine and badged every model `Won't fit`.

## The estimate

### Three numbers, not two

```text
need     = weights + mmproj + KV(window) + compute_buffers
resident = what the model must fit inside to run at full speed
refusal  = what physics allows at all
```

The two subtractions sit on opposite sides of the comparison, and collapsing
them into one `overhead` term is what made the first prediction wrong by 922 MiB.
Measured, Qwen3 4B at 16K on an RTX 3050 with 5,234 MiB free: treating the
1,028 MiB the fitter holds back as part of `need` predicts `FITS` with 378 MiB
spare, while llama.cpp actually spilled 602 MiB of weights and 320 MiB of KV.
Same numbers, opposite verdict, purely from which side of the comparison the term
sits on.

`resident` and `refusal` come from the budget rather than being assembled in the
estimator, because what they mean depends on the machine:

```python
@property
def resident_bytes(self) -> int:
    return self.usable_vram_bytes if self.has_gpu else self.ram_available_bytes

@property
def refusal_bytes(self) -> int:
    if not self.has_gpu:
        return self.ram_available_bytes      # nothing to spill from
    if self.uma:
        return self.ram_available_bytes      # one memory, never a sum
    return self.usable_vram_bytes + self.ram_available_bytes
```

where `usable_vram_bytes = device_free - fit_reserve`.

Assembling these in the estimator is what badged every model on a CPU-only laptop
as spilling from a graphics card it does not have. With no GPU the two are the
same number, which makes `PARTIAL` unreachable there by construction rather than
by a special case.

On unified memory the refusal threshold is **host memory**, not the device's own
figure, because Metal's working set bounds what Metal will allocate rather than
what the machine can hold. Measured: a 1.7B at 40960 projected 6032 MiB against a
5460 MiB working set, and llama.cpp ran it with 23 of 29 layers on the CPU
backend, which reads the same chips without that ceiling. So `PARTIAL` stays
reachable on a Mac, in the band between the pool minus the fit reserve and host
memory. Refusing it would remove a real option from the users with the least
choice.

### The fit reserve is a flag, not a prediction

```cpp
// common/common.h
std::vector<size_t> fit_params_target =
    std::vector<size_t>(llama_max_devices(), 1024 * 1024*1024);
```

**1 GiB per device, platform independent.** The Windows figure of 1,028.34 MiB
was that 1024 MiB plus allocator rounding. Metal names it out loud under `-v`:

```text
common_params_fit_impl: projected to use 5752 MiB of device memory vs. 5460 MiB of free
common_params_fit_impl: cannot meet free memory target of 1024 MiB,
                        need to reduce device memory by 1315 MiB
```

`5752 - (5460 - 1024) = 1316`. The comparison is exact, on a second backend, with
no fitting.

It is also a CLI flag, `--fit-target`, in MiB per device. So the reserve stops
being a number to predict and becomes an input we control: we pass it, and
`usable = device_free - fit_reserve` is true by construction on every platform,
including ones nobody has run. `fit_target_mib()` is the one place that value is
computed, and it is the same function the preset writes and the badge subtracts.

### The four terms

`itemise()` returns them separately rather than as a sum, for three reasons. A
sum is untestable, because it can be right for compensating wrong reasons. A test
can assert that the weights term does not move when the window does. And the
offload calculation needs to know which terms llama.cpp can actually move.

```python
@dataclass(frozen=True)
class NeedItems:
    weights_bytes: int
    mmproj_bytes: int
    kv_bytes: int
    compute_bytes: int
```

The projector is its own term because `--fit` does not count it, so a vision
model our sum calls resident can still fail to allocate, and because it is not a
thing the fitter can move.

### The KV cache

Architecture-derived and independent of how the weights were quantized, which is
what lets one header read price every build of a model. Three modules, one
question each.

**How wide one layer's entry is.** Ordinarily
`head_count_kv x (key_length + value_length) x bytes_per_element`. For a latent
model (`kv_lora_rank > 0`) it is `kv_lora_rank + key_length_mla`, one entry per
token per layer rather than a key and a value per head. Priced by the ordinary
formula, a DeepSeek-class header reads enormously too large, because it reports a
single KV head while the model has a hundred and more.

**Bytes per element** comes from the block layout, not from the bit width divided
by eight: `q8_0` stores 32 int8 weights plus one fp16 scale, so it is 34/32 bytes
per element and not 1.0.

| | f32 | f16 / bf16 | q8_0 | q5_1 | q5_0 | q4_1 | q4_0 / iq4_nl |
|---|---|---|---|---|---|---|---|
| bytes/element | 4.0 | 2.0 | 34/32 | 24/32 | 22/32 | 20/32 | 18/32 |

The load plan only ever chooses between `f16` and `q8_0`, and the preset writes
only those two. The rest are there because a searched model's own header can name
any of them and they have to be priceable.

**How many cells a layer allocates.** Not the same as the token count. Every
cache is padded to 256 cells on every backend, and a sliding-window layer is
sized as `pad(min(n_ctx, n_swa + n_ubatch))`, because a batch being processed has
to sit in the cache beside the window it attends to. `n_ubatch` is
llama-server's default 512 and `n_seq_max` is 1, pinned by the `parallel = 1`
every preset writes.

**Which layers hold the whole window.** `sliding_window.py` consults three
sources in the order llama.cpp itself does: a per-layer flag array in the header,
then a period in the header, then a per-architecture table of 14 entries read
from `load_swa_pattern` at `b11050`. An architecture nobody has verified is
deliberately **absent** from the table rather than guessed, and absence means
every layer is priced at full width, which over-states memory in the only
direction it is safe to be wrong in.

Layers that allocate a cache are `block_count - shared_kv_layers`. Gemma 3n and
Gemma 4 reuse an earlier layer's cache on their last blocks, so charging those
layers a cache each over-states the window's cost on exactly the models chosen to
be cheap on a small machine.

**The formula is exact, verified on both backends.** Qwen3 1.7B on Metal:
`2 x 28 layers x 8 kv_heads x 128 x 2 bytes x 16384` = 1792 MiB, reported as
`1792.00`, and 4480.00 at 40,960 cells. Qwen3 4B on Vulkan predicts 2304 MiB
against `1984 + 320` measured.

### Compute buffers

Absent from the formula entirely in the first draft, and then present as a
constant, which was nearly as wrong: scratch is sized by the widest thing one
layer computes, so it scales with the model rather than being a fee every model
pays alike. The constant was fitted to a 1.7B and under-stated a 4B by about
70 MiB, which is more than the margin that decides a 12 GB card's top row.

```python
activation_width = max(12 * n_embd,
                       4 * n_ff,
                       n_used * (2 * n_embd + 3 * n_ff_exp) + 3 * n_ff_shared)

flat  = int((activation_width * 512 + n_vocab * min(512, 1)) * 4 * SAFETY)
total = flat + 5_120 * n_ctx
```

with `SAFETY = 1.20` and `SLOTS = 1`, matching the `parallel = 1` in every preset.

The safety factor and the per-token slope are fitted, not derived, and the module
says so. Three measured points: Qwen3 1.7B on Metal reported 102.24 MiB at 16384
and 222.24 MiB at 40960, and a 4B on Vulkan reported 143.62 device plus 26.01
host at 16384. The slope is exact for the Metal pair, 120 MiB over 24,576 tokens.
The two backends disagree about the flat half by more than the widths explain, so
1.20 is fitted to cover both rather than to match either, and it over-states the
1.7B by about a third to do it. At 1.10 the 4B came out at 0.97 of what Vulkan
really allocated, and under-stating is the direction that ships a confident badge
about a model that spills.

A header that states no widths at all falls back to the old constant line,
23 MiB plus 5,120 bytes per token. Wrong in detail, but it is the measured floor
for the smallest model and certainly better than pricing scratch at nothing. The
manifest closes that door for curated entries by requiring `embedding_length` and
`feed_forward_length` to be present and positive.

### Offload counted in layers, not bytes

llama.cpp does not split a model by bytes. Its fitter fills devices with whole
layers, back to front, so the answer is a count of layers over the layer count:

```python
movable   = items.weights_bytes + items.kv_bytes
per_layer = movable / shape.block_count
fraction  = min(1.0, ceil(spilled / per_layer) / shape.block_count)
```

Only layers move. The projector is pinned by a flag rather than placed by the
fitter, and the compute buffer belongs to whichever device runs the graph, so
neither is part of what a layer costs.

Measured on an RTX 3050, Qwen3 4B spilled 602 MiB of weights plus 320 MiB of
cache, which is 0.19 of the model. The byte ratio said 0.12 and this gives 5/36,
0.14. All three agree on the verdict and on the ordering, but the fraction grades
the reason line and gates the recommendation, so it is the fraction that has to
be right.

### Fit states

There is no `unknown`. Every row has a file size, so every row has a badge.

| State | Condition | At load |
|---|---|---|
| `FITS` | `need <= resident` | every layer on the device, full speed |
| `PARTIAL` | `resident < need <= refusal` | `--fit` places some layers on the CPU; runs, slower |
| `TOO_BIG` | floor `need > refusal` | physics refusal, the only state that blocks install |

`TOO_BIG` is evaluated at `CONTEXT_FLOOR_TOKENS`, not at the requested window: a
model that will not fit at the floor cannot be rescued by a smaller context, and
the remedy to offer is a smaller build.

There is one more `TOO_BIG` path, found by the property sweep rather than by a
fixture. When `need > refusal` at the *requested* window but the floor fits, the
window is refused rather than described as a partial offload. It is reachable
only where residency and refusal are the same number, which means a machine with
no GPU, where the model is already entirely on the processor and calling it
partly offloaded would name a device that is not there.

`offload_fraction` is kept on the verdict and never collapsed into the state.
`PARTIAL` spans everything from barely noticeable to unusable, and the number is
already known from the same subtraction that produced the state.

`CONTEXT_FLOOR_TOKENS` is **8192**, not llama.cpp's own 4096 reduction floor.
4096 is too short once a system prompt, retrieved excerpts and a reply share the
window, so the fit search would settle there rather than spill weights it could
spill instead. What makes 8192 safe rather than merely smaller is
`modules/chat/budget`, which sizes every part of a prompt from `n_ctx`; see
**The context budget**.

### Speed tiers: one classification

A badge and a recommendation both start from the same `FitVerdict`, and both used
to threshold its raw `offload_fraction` independently. The badge drew lines at a
quarter and a half to choose wording; the recommendation drew a separate line at
three quarters to choose whether to star a build. Nothing connected the two, so a
build could be starred while its own badge read *"Too big for the GPU, so part
runs on the CPU"* or worse.

`fit/speed.py` is now the only module that thresholds that number:

```python
TOO_BIG          state is TOO_BIG
HEAVY_SPILL      f >= 0.5
MODERATE_SPILL   0.25 < f < 0.5
LIGHT_SPILL      f <= 0.25
FULL             state is FITS

RECOMMENDABLE_TIERS = {FULL, LIGHT_SPILL}
```

Collapsing both callers into one ordered tier removes the second line rather than
moving it. A recommended build can now only ever carry *"Full speed"* or *"Most
of it still fits"* wording, by construction rather than by two independently
tuned numbers staying in step.
`test_badge_matches_the_load.py` holds it with a property test sweeping every
curated model against every budget shape.

### Badges

A badge is a verdict plus one plain line of why. The verdict is what someone
choosing a model needs (fast, slower, or impossible); the mechanism is the
explanation, not the headline. Wording branches on two facts the budget already
carries, `uma` and `has_gpu`, and never on the runtime's name.

**Discrete GPU**

```text
●  Full speed        Runs entirely on your graphics card
◐  Reduced speed     A little too big for the graphics card. Most of it still fits.
◐  Reduced speed     Too big for the graphics card, so part runs on the processor.
◐  Reduced speed     Well over the graphics card's memory. Expect it to be slow.
○  Won't fit         Needs about 21 GB. This PC has 13.6 GB
```

**Apple Silicon** swaps "the graphics card" for "the GPU", "the processor" for
"the CPU", and "This PC" for "This Mac".

**No GPU** collapses to two states, because `PARTIAL` is unreachable:

```text
●  Works here        Runs on your processor
○  Won't fit         Needs about 21 GB. This PC has 16 GB
```

Three wording decisions that look small and are not.

**"Full speed", not "Fast".** Fast is a promise the badge cannot keep: a 32B
running entirely on a 4090 is still slower than a 4B. *Full speed* is relative to
the model, which is exactly what the state means.

**"Works here" on a machine with no GPU.** Technically that case is `FITS`, but
*Full speed* reads as a boast about a slow situation when there is no faster
alternative to contrast with. The useful information is simply: yes, you can run
this.

**Sizes are decimal GB with one decimal, trailing zero dropped**, so a pair reads
"21 GB" and "13.6 GB" rather than "21.0 GB" and "14 GB". Rounding the second to a
whole number loses the half gigabyte that decided the answer.

> **Copy rule for every user-facing string in this phase: no em dashes and no
> hyphens.** Commas, full stops or parentheses. Applies to badges, empty states,
> error copy and the recommendation line.

### The load plan

`plan_load()` decides the window and the cache precision once, because context is
fixed at load and cannot be renegotiated mid-conversation.

```python
ceiling = shape.context_length or CONTEXT_FLOOR_TOKENS
floor   = min(CONTEXT_FLOOR_TOKENS, ceiling)
CONTEXT_RUNGS = (8192, 16384, 32768)
```

**Prefer residency over window.** KV is allocated upfront and competes with the
weights, so maximising context silently demotes a model out of GPU residency.
The search widens only while the verdict stays `FITS`.

**Prefer `f16` over `q8_0`.** Quality is identical, but a quantized cache
requires a working flash-attention kernel, and where one is unavailable llama.cpp
falls back to CPU attention silently. `resident_precision()` returns the cheapest
cache that keeps the build resident, or `None` when none does, in which case the
plan holds the floor at `f16`: a cheaper cache buys nothing once layers are
spilling anyway, so it would take the flash-attention dependency for no gain.

`planned_precision()` is the same rule with a fallback, and it is what
`rows.py`, `recommendation.py` and `service.repo()` all call. Before that shared
rule existed, the badge priced `f16` while the loader chose `q8_0`, so a row read
*Reduced speed* for a model the runtime then placed entirely on the device.

**A fixed set of rungs rather than a continuous search**, so the whole surface of
windows a person can see is something a test can enumerate. The model's own
trained length is tried too when it falls between two rungs, so a model is not
held below what it was actually trained for, and the floor is always a candidate
so the search never returns nothing.

**Two budgets, and widening stays inside the tighter one.** `budget` is capacity
and decides the verdict, so the plan agrees with the badge the catalog already
showed: a machine that is busy this second has not become one that cannot run the
model. `live` caps widening only, because context past the floor is
opportunistic. A cap must not raise a ceiling, so widening takes whichever budget
has less headroom. Widening against a more generous `live` and then reporting
against `budget` produced a plan that said `PARTIAL` for a row the catalog had
badged `FITS`.

## The catalog

### Two tiers

| | Curated | Search |
|---|---|---|
| Source | `curated-models.json`, shipped frozen | `huggingface.co` |
| Network | none, ever | required, egress gated |
| Priced from | committed `shape`, on first paint | file size, then the header on open |
| Carries a `rank` | yes, never displayed | no |
| Can be recommended | yes | no |

Two endpoints, deliberately. Curated plus installed renders offline and
instantly; search is paged and needs the network. One response covering both
would either block on the network or return partial results behind a flag, and
that flag is the `scanned` flag this phase deleted.

### The manifest, schema 4

`curated-models.json` is **source, not build output.** A person runs the
authoring script, reads what it proposes, and commits the result. A rank moving
78 to 94 shows up in a pull request where someone notices; a tag rebuilds to the
same manifest forever; and the cadence is honest, since these change when someone
adds a model rather than when someone cuts a release.

```jsonc
{
  "model_id": "Qwen/Qwen3-8B",
  "family": "Qwen3",
  "label": "Qwen3 8B",
  "parameter_count": "8B",

  // DERIVED, per model. The script writes all of it, no human input ever.
  "shape": {
    "architecture": "qwen3", "block_count": 36,
    "head_count_kv": 8, "key_length": 128, "value_length": 128,
    "context_length": 40960, "n_vocab": 151936,
    "embedding_length": 4096, "feed_forward_length": 12288,
    "sliding_window": 0, "expert_count": 0,
    "expert_feed_forward_length": 0, "expert_shared_feed_forward_length": 0,
    "expert_used_count": 0, "sliding_window_pattern": 0,
    "sliding_window_layers": [], "shared_kv_layers": 0,
    "kv_lora_rank": 0, "key_length_mla": 0
  },
  "capabilities": [],       // user facing only: "vision" or nothing
  "decode_fraction": 1.0,   // 1.0 dense; the active slice for a mixture of experts

  "variants": [
    {
      // DERIVED
      "repo": "unsloth/Qwen3-8B-GGUF",
      "file": "Qwen3-8B-Q4_K_M.gguf",
      "quantization": "Q4_K_M",
      "size_bytes": 5027784512,
      "mmproj": null,

      // JUDGEMENT. Three fields, typed by a person, beside the build they judge.
      "rank": 78,
      "rank_basis": "llmfit-1.1.11",
      "validated": false
    }
  ]
}
```

**The split is the point.** Everything marked DERIVED comes free from the GGUF
header and the Hugging Face listing; everything marked JUDGEMENT is three small
decisions a person makes in a minute. That is what keeps the manifest
maintainable at twenty entries instead of six.

**`shape` is what makes the curated tier work offline.** Pricing a model means
reading its GGUF header, and a curated entry is not downloaded yet, so without
these fields an airgapped machine would have no fit badge on the one tier it can
use.

**`embedding_length` and `feed_forward_length` are required**, unlike their
optional counterparts on `ModelShape`. A committed entry is authored by a script
that read a real header, so a missing width here means a manifest written by hand
or by an older script, and the compute buffer would quietly price it as though
the model had no layers to compute. The app refuses to start on that rather than
shipping a confident wrong badge.

**`rank` lives inside the variant** because quality is a function of (model,
quantization), not of the model alone: llmfit returns 75, 78, 81, 82, 83 for
Qwen3 8B at Q3_K_M through Q8_0. A rank at the top level describes a build
without naming it, and that is not hypothetical, since an earlier draft carried
five ranks taken at Q8_0 while the manifest pinned Q4_K_M. Nested, the mismatch
is impossible to express.

`validate_manifest` rejects a wrong `schema_version`, a duplicate `model_id`, a
duplicate `(repo, file)` pin, and **more than one distinct `rank_basis`**, so
ranks from two scales are never silently sorted together.

The shipped six, all Qwen3, all `Q4_K_M`, `rank_basis` `llmfit-1.1.11`:

| model | file | rank |
|---|---|---|
| Qwen3 0.6B | 396,705,472 B | 33 |
| Qwen3 1.7B | 1,107,409,472 B | 48 |
| Qwen3 4B | 2,497,281,312 B | 63 |
| Qwen3 8B | 5,027,784,512 B | 78 |
| Qwen3 14B | 9,001,753,984 B | 85 |
| Qwen3 32B | 19,762,150,048 B | 92 |

### Authoring

`scripts/refresh_curated_models.py`, run by hand, **never in CI**. The three
judgement fields live in an `ENTRIES` table in the script where a person edits
them; everything else is derived from the live listing and a real header read.

`scripts/curated/` holds the derivation: `huggingface.py` resolves a repo and
file and reads the header, `projector.py` finds an `mmproj-*.gguf` sibling and
prefers F16 over BF16 over Q8_0, and `tensor_bytes.py` computes
`decode_fraction`.

`decode_fraction` is the fraction of a build's bytes read per decoded token, 1.0
for a dense model and the active slice for a mixture of experts. It is computed,
not typed:

```text
decode_fraction = (non_expert_bytes + expert_bytes x used / experts) / total_bytes
```

Both halves of that come from llama.cpp rather than from conventions restated in
our tree: sizes from `GGML_QUANT_SIZES`, and the expert tensor set from
`TENSOR_NAMES`, matching the same seven members llama.cpp's own fitter matches
with `blk.\d+.ffn_(up|down|gate_up|gate)_(ch|)exps`. Deliberately not
`ffn_norm_exps`: a per-expert norm is a vector beside these matrices, and the set
that decides what llama.cpp moves to the host is the set that decides what it
reads from the host.

Every shipped entry is dense and carries `1.0`. It is computed now anyway because
it is free from the header, and because without it a mixture-of-experts entry's
speed prediction would be wrong by roughly an order of magnitude the moment such
a rung lands.

**What triggers a refresh**, realistically four or five times a year: a model
worth recommending ships; a quantizer deletes or re-uploads a pinned file so
users hit a 404; the pinned llama.cpp build is bumped and pins want reverifying;
a hardware class turns out to be under-served; or someone reports a bad
recommendation.

### Ranking

`rank` does two things and nothing else: it orders the curated rows, and it
selects the star. It is never displayed, never compared outside the app, and
never applied to a searched model. Because it is only ever a sort key it does not
need to be a measurement, it needs to be an **order**. Hence `rank`, not
`quality`: calling it quality would imply we measured something we did not.

**It means "good at this app's job"**, answering from the user's documents with
citations that resolve, not general capability. That distinction does real work:
llmfit rates Qwen2.5-Coder 7B at 89 against Qwen3 8B's 83, because it is
measuring coding ability, and for document Q&A the coder is the weaker model.

**llmfit proposes; a person decides.** It carries real model-specific signal:
grouping about 4,000 scored models by (parameter count, quantization), 224 of 230
groups show quality varying between models of identical size and quant, so it is
not parameter count in disguise. But it is unreliable on models it does not know
well, returning a perfect 100 for community fine-tunes with names like
`Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-NV`, above published models.
That number is closer to the name than to measured behaviour. The shipped six
come back 33, 48, 63, 78, 85, 92: monotonic and sanely spread, which is the
population the curated tier draws from.

Four checks before committing a rank: within a family it should rise with
parameter count; anything at or near 100 is suspect; across families cross-check
a public leaderboard, which is the comparison llmfit is least reliable at; and a
specialist is ranked for *this* task, not the one it was tuned on. If llmfit has
no entry or proposes something absurd, type the integer by hand. The field is an
`int` and nothing requires llmfit to have produced it.

**If llmfit disappears tomorrow**, committed ranks are unaffected, the schema is
unaffected, the refresh script loses its proposer, and the app never knew about
it. That is the test a long-term dependency should pass, and the reason to keep
it outside the product.

**Vision is a capability, not a rank position.** Nobody chooses a vision model
instead of a general one; they need one when the documents are images. So the
star stays "the best-ranked build that runs well", and a vision entry surfaces
when it is relevant, never as a competitor in the ordering.

**Staleness is acceptable by design.** Airgapped means no refresh path, so a
shipped list ages. That would be fatal if curated were the only way to get a
model, and it is not: 204,797 models are one search away, badged and installable.
Curated ages into "a starting point we tested a while ago" rather than a
boundary.

> **Long-term destination, not this phase.** llmfit grades general capability.
> SurfSense needs something narrower: does this model answer from the user's
> documents, and cite the right chunks? No external leaderboard measures that.
> The honest end state is a small internal eval, 20 to 40 fixed questions over a
> fixed document set, run through the real chat path and scored on whether the
> answer came from the sources and whether `[n]` citations resolved, with `rank`
> set from that.

### Search

```text
GET /api/models?filter=gguf&search=<q>&sort=downloads&direction=-1&limit=<=50&full=true
GET /api/models/{repo}/tree/main?recursive=true
GET /api/models/{repo}?expand[]=gguf
```

300 s cache, because Hugging Face allows 500 requests per 5 minutes and a search
list is re-fetched on every keystroke a debounce lets through.

**Sorted by downloads**, which is the only sort usable as a default. All five HF
sort fields work on `filter=gguf`; `likes` and `trendingScore` surface
uncensored derivatives in the top few, and `lastModified` and `createdAt` surface
half-finished uploads. Every order surfaces abliterated fine-tunes somewhere near
the top, which is what an open catalog means and is not a reason to reintroduce
grading. The count is presented as popularity, never as endorsement.

**One denylist, fed by two facts.** The install gate lives in
`modules/llm/catalog/search/not_chat.py`: a single table of 88 names, grouped by
what a model *is* rather than by which fact named it, so a GGUF architecture and
a Hugging Face pipeline tag share it. `refusal(architecture, pipeline_tag)` looks
both up and returns the sentence a person reads, or nothing.

**Why a denylist rather than an allowlist.** The two age in opposite directions.
An incomplete allowlist refuses a model that works and nobody finds out, because
the user is told no and believes it. An incomplete denylist admits a model that
does not work, which announces itself. llama.cpp adds architectures faster than
any list is updated, so the default has to be yes.

> **This was learned the expensive way.** The gate began as one hand written set
> and had drifted in both directions at once. It refused 43 architectures the
> runtime supports, including Gemma 4, Qwen 3.5 and Mistral 3, telling the user
> llama.cpp could not run a model it demonstrably runs. It admitted `bert`,
> `nomic-bert`, `t5encoder` and five more that abort the worker on the first
> message. Three entries were misspelled, `granite-moe` for `granitemoe` among
> them, so they had never matched anything and nothing could say so.

**The tag is there because a header can be honest and still mislead.** Measured
across the 1000 most downloaded GGUF repos, an embedding model declares
`mistral3`, a voice model and a reranker both declare `qwen3`, and a video
encoder declares `qwen35`. Structurally those *are* those architectures, so
refusing them would refuse Mistral and Qwen. Only the repo's own tag separates
them, and it rides along on the listing call already being made as one more
`expand[]` parameter, costing no extra request.

**A denylist, not a tag requirement.** Counted on `library=gguf`, the pipeline
tags cover roughly 43,500 of 204,797 repos, so about 80% carry none. Requiring a
tag would hide four fifths of the catalog. An absent tag is an absent answer, and
only the tags named in the table refuse.

The tags that mean chat are held out by a test and must never be added:
`text-generation`, `image-text-to-text`, `video-text-to-text`,
`audio-text-to-text` and `any-to-any`. `image-text-to-text` alone is 28% of
admitted repos, every Qwen 3.5 and every Gemma 4, so denying it would empty the
search screen.

**What it costs.** Measured over the same 1000 repos: 18 of 979 install and then
fail, all brand new chat architectures that no denylist can name in advance,
because by the time the name is known llama.cpp has usually merged support and
the entry would have to be removed again. `MODEL_CANNOT_RUN` covers that case
with "SurfSense cannot run this model. Pick another model.", which is a statement
rather than the retry advice a 500 used to produce.

**`scripts/audit_gate.py` is what keeps the list honest.** The generated table
used to allow a test that held every denylist key against the names llama.cpp
defines, which is how the three misspellings were found. With no table, the audit
replaces it: it runs the gate over the top N repos, prints every refusal for
review, and prints entries that matched nothing, which is what a typo looks like.
It needs the network, so it is never part of the test suite.

**Eligibility is read before the header.** Hugging Face has already parsed a
GGUF's header and serves the result under `expand[]=gguf&expand[]=pipeline_tag`,
giving the architecture, the context length, whether a chat template exists and
what the repo says the model is for. Asking that first means a model that cannot
chat costs no range request against a file we were never going to install. It
does not carry the KV shape, so it replaces nothing for a model we *can* run: the
header read still happens, it just no longer happens for models we cannot.

**The file is asked, not the repo.** Hugging Face parses **one** file per repo
and serves that as the repo's answer, so a chat model shipped beside an `mmproj`
sidecar came back as `clip` and the whole repo was refused, 17 of 979 top repos
among them and 13 of those vision models. Each was told to install the model it
belonged to, which was that repo. Nobody could learn otherwise, because being
told no is indistinguishable from a considered answer.

So `service.repo()` reads the candidate build's own header and gates on that.
`_candidate()` walks the builds until one is both a model and one the denylist
allows, because `list_builds` orders by size and a draft head is always smaller
than the model it accelerates: judging the first file would reproduce the same
failure from our own ordering. Normally one read; two or three in a repo whose
sidecars sort first.

**Refusing became the cheap path.** `source.py` widens from `PROBE_BYTES`
(256 KiB) to 8 MiB to 24 MiB. A projector, an imatrix or a diffusion GGUF has no
tokenizer, so its metadata ends inside the probe and `general.type` names it
outright. A chat model's `tokenizer.ggml.tokens` runs to megabytes, measured at
5.93 MB for Qwen3 0.6B and 7.82 MB for Llama 3.2 1B, so it truncates there and
widens to exactly what it read before. The truncation is the verdict: a header
that does not fit belongs to a real model.

`modules/llm/gguf/file_kind.py` reads only official keys, `general.type` against
`gguf.constants.GGUFType`, plus `split.count`. A header that parses and names no
architecture at all is `NOT_LOADABLE`, because that key is what llama.cpp
dispatches on. Everything else fails open: a short read, a failed request, an
unparseable file all admit, since a refusal made from a failure to read is the
one mistake this tier cannot afford.

A repo that cannot chat here still lists its builds at their real sizes, badged
`Cannot run` and not installable, because the screen is answering "what is in
here" as well as "can I run it", and an empty repo reads as a broken page rather
than an unsupported model.

A repo that ships **no chat template** is installable and warns. It will answer
badly in a chat UI, which is a real warning and not a fit state.

**A header that cannot be read does not lose the repo.** The builds fall back to
a size-only shape, every architecture-derived term goes to zero so `need` is the
file size and nothing else, and the rows are marked `approximate` so the screen
can say so. Refusing the whole repo over one unreadable header would hide builds
the user can run.

**What a search row shows**: fit verdict, size per quantization, architecture,
context length, chat template present, license, gated, downloads, likes, last
updated, and provenance. Provenance is free and worth surfacing: 32 of the top 40
GGUF repos carry a `base_model:quantized:<repo>` tag, so a row can say where the
file came from. That is a fact about provenance, not a grade, and it is most of
what a quality score was doing for a reader. The 8 of 40 without one are
informative by their absence.

`list_builds()` excludes split sets (`-of-`), projectors (`mmproj`) and draft
models (`draft`): none of them is a thing a user installs on its own. It is a
**display filter and decides nothing**. Eligibility comes from the candidate's
header, and the walk moves on when this filter kept something it should not
have, so a name being wrong costs a row on a page rather than a refusal. The
quantization comes out of the filename with a regex tight enough to require a
real quant token, because matching loosely reads `Qwen3` out of
`Qwen3-Coder-30B-A3B-Instruct-UD-TQ1_0.gguf`, seen live. The last match wins,
because the quant is conventionally the final token.

### Install ids

`POST /llm/install` keys on a `catalog_id`, and
[`../frontend/05-install-ux.md`](../frontend/05-install-ux.md) requires the
renderer to send only that: no repo, file, artifact URL, local path or
quantization. A curated row's id comes from the manifest; a search hit has no
manifest entry, so there is nothing to key on. Closing that by letting the
renderer post a repo and file would hand the frontend the ability to name an
arbitrary download, which is exactly the capability the install contract exists
to withhold.

So the server mints ids for both tiers and hands back only the id.

- **Curated**: `secrets.token_urlsafe(18)`, minted once per process, keyed on
  `(repo, file)`. Opaque so the renderer cannot assemble one.
- **Searched**: an `InstallTicket` with a 300 s TTL, the same window the search
  cache uses. A ticket outliving its row would let a stale screen install
  something the user is no longer looking at.

`resolve_install()` checks curated ids first and then tickets, and cannot tell
them apart from the route's point of view. Both failure modes collapse into the
existing `422 catalog id is stale or unknown; refresh the catalog`, because it is
the same failure and already has copy.

### List order and the recommendation policy

Curated sorts by `(fit state, -rank, model_id)`: fit coarsely, rank finely.
Sorting by rank alone would put a refused 32B at the top of a small machine's
screen, which is the one thing a model chooser must not do.

**One row per model, not per variant.** A model with two builds is one row, which
takes the best state and rank among them and installs the build that produced
them. Listing builds separately would show the same model twice on a screen whose
job is choosing a model.

**Neither list displays a rank.** `CatalogRow` does not carry one, `schemas.py`
does not declare one, and `router._row()` does not serialise one. The surest way
to keep "never displayed" true is for the renderer never to receive it.

```python
def recommend(curated, budget) -> Recommendation | None:
    candidates = [
        (entry, variant, verdict)
        for entry in curated
        for variant in entry.variants
        # at the cache the loader would actually choose
        for verdict in [estimate(..., precision=planned_precision(...))]
        if speed_tier(verdict) in RECOMMENDABLE_TIERS
    ]
    return max(candidates, key=lambda c: (c.variant.rank, -c.variant.size_bytes),
               default=None)
```

`TOO_BIG`'s own tier is never in `RECOMMENDABLE_TIERS`, so that is the one check:
physics and speed are judged by the same classification rather than a state check
plus a separate threshold.

**`None` is an honest answer rather than a failure.** Every build physics does
not refuse stays installable; it simply goes unstarred. The one case where that
was wrong has been fixed: a CPU-only machine used to have every row come back as
a full spill, which the gate then refused, so the one screen whose job is
choosing a model chose nothing on the hardware that most needs the help. Splitting
residency from refusal made `PARTIAL` unreachable there, and the star came back.

**The policy ranges over builds, not models**, because a build is what the user
installs and what `rank` describes. With one variant per entry the cross-product
is the entry list and the behaviour is identical, but writing it this way is the
difference between adding a second build later as a manifest edit and rewriting
the module, its tests and every fixture.

**Why the gate is on speed rather than on residency.** Residency is a mechanism
and speed is the goal, and they coincide on a large card and diverge on a small
one. Measured on an RTX 3050, Qwen3 4B spills about a fifth and Qwen3 8B about a
quarter, and the machine's owner runs the 8B without noticeable lag. A
`FITS`-only rule stars a 1.7B on that machine, which is not conservative, it is
wrong: it bans a configuration that demonstrably works.

The reason a fifth spilled is barely noticeable is that decode is
bandwidth-bound and the split is not proportional. Measured, using `-ngl` to set
the fraction directly so model size is held constant:

| layers on GPU | `f` | prefill ratio | decode ratio |
|---|---|---|---|
| 36/36 | 0.00 | 1.00 | 1.00 |
| 28/36 | 0.22 | 0.81 | 0.63 |
| 18/36 | 0.50 | 0.67 | 0.38 |
| 0/36 | 1.00 | 0.50 | 0.25 |

Fully on the CPU, prefill still runs at half device speed while decode drops to a
quarter. This app is prefill-dominated, roughly 8,000 prompt tokens against 300
decoded, so a turn loses substantially less to spilling than any decode-focused
benchmark implies. That is also why no threshold borrowed from an agent-shaped
application belongs here.

> **Open tension, stated rather than smoothed over.** The measured claim above
> is that the 3050's owner runs the 8B happily at a byte ratio of about 0.28. The
> layer-granular fraction puts that same configuration at 0.33, which is
> `MODERATE_SPILL`, which is not recommendable, so the current policy stars the
> 4B on that machine. Either the tier boundary is a little tight or the measured
> experience was generous, and one prefill measurement settles it. The boundary
> is not a physical constant, and it is deliberately the same number the badge
> uses, so moving it moves both together.

## The wire

### HTTP routes

| Route | Returns | Network |
|---|---|---|
| `GET /llm/system` | budget, devices, `gpu_status` | none |
| `GET /llm/catalog` | budget, `gpu_status`, curated rows, installed rows, `recommended_model_id` | **none** |
| `GET /llm/search?q=&limit=` | HF hits, described not judged | `huggingface.co` |
| `GET /llm/search/{repo:path}` | builds with exact sizes and badges | `huggingface.co` |
| `POST /llm/install` | NDJSON progress stream | `huggingface.co` |
| `DELETE /llm/models/{model_name:path}` | `ModelDeleteRead`, `selection_cleared` | none |

`GET /llm/search/{repo}` is where the header read happens, so the trigger is
**opening a search result**, not hovering or typing. The list-level badge stays
approximate until then.

Unchanged: `GET /llm/providers`, `GET /llm/providers/{provider}/models`,
`GET|PUT /llm/selection/{role}`, `GET|POST /llm/onboarding`, everything under
`/llm/connections`, and the four `/llm/image/local*` routes, which are a separate
runtime with its own lifecycle and are out of scope here.

Deleted with the Ollama adapter: `GET /llm/providers/{provider}/catalog` and
`POST /llm/providers/{provider}/pull`.

Search and repo routes guard on `egress.MODEL_SEARCH` and install on
`egress.MODEL_DOWNLOAD`, and an unreachable host is a `503` naming the
destination rather than a generic error. With egress off, search is **absent
rather than degraded**, which is the airgapped product: curated, installed and a
local `.gguf` import all still work.

### Response shapes

`SystemRead` and `CatalogRead` both carry `budget` and `gpu_status`.
`CatalogRowRead` carries `fit` (state, need, budget, offload fraction,
approximate), `badge` (verdict, reason), `capabilities`, `installed`, `selected`,
`can_install`, `recommended`, and an opaque `catalog_id`. `RepoRead` carries
`architecture`, `context_length`, `supported`, `chat_template`, an optional
`ineligible_reason`, and a list of `BuildRead`. **No row of any kind carries a
`rank`, and no response carries a `scanned` flag**, because there is no scan: the
budget comes from the allocator in milliseconds.

### The install stream

NDJSON, `{"type": …}` frames, one per line:

```text
starting     "Preparing download"
downloading  completed / total, repeated
verifying    "Checking the model"
preparing    "Preparing the model runtime"        <- reprice(), then wait
selecting    "Selecting model"                    <- only when select: true
complete     "Model is ready"
             or "Downloaded. It becomes available once the runtime restarts."
error        "The model could not be installed. Retry the download."
```

The download writes to a sibling `.part` file and renames only once the whole
file is present and verified, so the router never discovers a partial model, and
a cancelled download keeps the `.part` for a later resume. A server that ignores
our `Range` header is detected by the absence of a `206`, and the bytes already
held are discarded rather than appended to.

One install at a time, enforced by an `asyncio.Lock` and a `409` when it is held:
two concurrent downloads compete for the same disk and the screen has one
progress bar.

## Chat

### The context budget

`HISTORY_BUDGET_TOKENS` used to be a constant with no relationship to `n_ctx`,
which was safe only while the window was always the same number. Lowering the
floor to 8192 made it unsafe, so `modules/chat/budget.py` prices the four named
parts of a turn against the real window:

| Part | Tokens | Basis |
|---|---|---|
| Answer reserve | 1024 | Reserved first. llama.cpp stops a reply wherever the window runs out, so spending this on history is how a good answer gets cut off mid-sentence with no error at all. |
| System prompt | 400 | A rendered prompt plus the grounding header at the largest tier. Approximate; the exact figure is one `/apply-template` call away. |
| Excerpts | 2400 | The retrieval cap already limits chunks to 480 tokens at up to 5 hits, so this holds even before retrieval runs. |
| Question | 1024 | `MessageText` enforces this at the wire. |

History gets whatever is left: `max(0, n_ctx - 4848)`, which is 3,344 tokens at
the 8192 floor and grows with the window. A narrower window therefore means a
shorter history rather than a turn that silently exceeds the window.

**An unknown window is not a narrow one.** A remote endpoint that does not report
`n_ctx` is an absent fact, not a small number, so the fallback is the previous
constant, 3000, unchanged. For the same reason `answer_max_tokens()` returns
`None` there: capping a reply to this app's reserve on an endpoint whose real
window might be far larger would truncate answers for a limit that was never
theirs.

### Counting tokens

`Generator.token_count()` prices a turn by the model's own tokenizer through
llama.cpp's `/tokenize`, proxied to the loaded worker the same way `/props` is.
The fallback heuristic was about 4 characters per token, which under-counts dense
text by 15 to 20%.

`None` is the answer for anything short of a clean count: no such endpoint, a
transient failure, or a model this generator does not run. A caller must fall
back to an estimate rather than read `None` as zero tokens, and `build_messages`
never mixes the two within one turn.

A remote endpoint has no equivalent, so `OpenAICompatibleChatProvider` keeps the
heuristic exactly as before.

### Capabilities and the system role

Two sources, two kinds of fact, and only one of them reaches a person:

```text
GET /models  -> architecture.input_modalities    what the model can ACCEPT
GET /props   -> chat_template_caps               what the TEMPLATE supports
```

Template-derived rather than guessed from a name. A regex over model names is how
you end up telling someone a model reads images when nothing can hand it one.

`supports_system_role` is read generously, defaulting to `True` when absent,
because a runtime that does not report it is more likely to be old than to be
incapable, and dropping the system message takes the grounding and the citation
instructions with it while the model answers exactly as confidently as it would
have otherwise. Where a template genuinely has no system role, `for_template()`
folds the system content into the first user turn rather than losing it. The
adapter downgrades at that seam so `modules/chat` never learns that templates
differ.

`vision` requires **both** halves: `IMAGE in inputs` and `typed_content`. A model
can accept images architecturally while its template takes only string content,
which leaves no way to send it one. It is the only capability that reaches the
UI; `system_role`, `typed_content` and `tools` are constraints that change how a
request is built and mean nothing to a person.

### Vision: what is built, and what is missing

**A vision model is two files.** The weights answer questions and the projector
turns a picture into something the weights can read. Every vision repo ships
both, and `list_builds` offers only the first, because a projector is not a
thing anyone installs on its own.

**Today a vision model installs and gives a text chat.** `install()` fetches one
file, the build the user chose, so the projector stays on Hugging Face.
`projector_for` finds nothing beside the model, `mmproj_bytes` is 0, the preset
carries no `mmproj` line, and `llama-server` loads the weights alone. Search
prices it the same way, so the badge, the preset and the load all agree: this is
a text model.

That is deliberate rather than unfinished. Nothing can send an image, so
fetching the projector would cost roughly a gigabyte of disk and its bytes of
device memory for a file that would be loaded and never touched. Consistency is
worth more than readiness here: a projector on disk with no way to use it would
make every memory estimate wrong by its size.

**What is already built and dormant**, each tested, waiting only for a second
file to exist on disk:

| | |
|---|---|
| `providers/llamacpp/projector.py` | finds the projector paired with a model |
| `providers/llamacpp/preset.py` | emits `mmproj = <path>` |
| `fit_target_mib()` | raises the fitter's margin by the projector's bytes, because `--fit` allocates it after placing layers and does not count it while deciding. Measured: a 600 MiB projector gives `fit-target = 1624` |
| `fit/itemisation.py` | prices `mmproj_bytes` as its own term |
| `capabilities.py` | `can_see`, gated on both halves |

**What has to be added**, in order:

1. **`InstallPlan` gains the projector.** It is `model_id, repo, file, size_bytes`
   today. The repo listing already names the file, and
   `scripts/curated/projector.py` already encodes the preference order, F16 over
   BF16 over Q8_0.
2. **`install()` fetches both files.** One extra `download_gguf` into the same
   directory. From that point everything above starts firing on its own.
3. **Search pricing passes `mmproj_bytes`.** `service.repo()` calls `estimate()`
   without it, so a vision build is currently priced as though the projector
   were free. `reprice()` already passes it. Both must agree or the badge
   promises a fit the load does not deliver.
4. **The chat request carries an image.** This is the real work and the only
   part with nothing behind it: no `image_url` anywhere in the request path and
   no attach control in the UI. `typed_content` from `chat_template_caps` is
   what says whether a given model's template can accept one.

**Check before starting.** A vision model should not show a `vision` badge
today, because `read_capabilities` derives it from what the loaded server reports
it accepts, and with no projector loaded that should be text only. This has not
been verified against a running server. If the badge does appear, that is the
worst intermediate state available: the catalog promising picture support while
the chat screen offers no way to send one. Fix that before anything else here.

**Audio is one step further back.** llama.cpp supports audio input through the
same mechanism, `clip.has_audio_encoder` and the whole `Keys.ClipAudio` group,
but `Modality` carries only `TEXT` and `IMAGE`, so an audio capable model is not
even detected as one. Out of scope, recorded so it is not mistaken for an
oversight.

### Constrained decoding

48 of the 69 prompt files demand a JSON object. `response_format` with a
`json_schema` masks every token that would produce invalid JSON, so a malformed
answer stops being something to repair and becomes something that cannot be
emitted. Chat prose is deliberately unconstrained.

The schema is not injected into the prompt. Fields are still described, once,
because compliance no longer depends on persuasion.

## Packaging

`electron/scripts/fetch-llamacpp.mjs`, pinned to build `b11050` **and to a
SHA-256 per target**, which closed the gap left by the previous fetcher.

| Target | Asset | Size |
|---|---|---|
| darwin-arm64 | `bin-macos-arm64.tar.gz` | 11.2 MB |
| win32-x64 | `bin-win-vulkan-x64.zip` | 31.8 MB |
| linux-x64 | `bin-ubuntu-vulkan-x64.tar.gz` | 30.4 MB |

The Vulkan archive is the CPU archive plus exactly one file, and all CPU
micro-architecture variants ship inside: 15 on Windows, 10 on Linux. The staging
step prunes to `llama-server` plus its libraries, 24 executables down to 1, which
also shrinks the macOS notarization surface.

- **Linux**: `libggml-vulkan.so` has `DT_NEEDED: libvulkan.so.1`. The deb adds
  `libvulkan1` to `Depends`; the AppImage bundles the loader or accepts CPU,
  since the ICD must come from the host driver.
- **`ubuntu-22.04` is pinned** in the workflow. `ubuntu-latest` migrates and
  would silently raise the AppImage's glibc floor.
- **Windows**: `vulkan-1.dll` is present in `System32` on a stock install, so
  nothing needs bundling. `taskkill /PID <pid> /T /F` walks the router's tree;
  verified with a model resident at `b11050`, four processes terminated depth
  first with no survivors.
- **macOS and Linux** reap through process groups and signals rather than
  `taskkill /T`.

`bundling/api.spec` ships `modules/llm/catalog/curated-models.json` at
`modules/llm/catalog`. It is read by path, so the analyser cannot see it, and the
path is asserted by a `packaging`-marked test because the previous value pointed
at a directory this branch deleted.

## Failure behavior

- **Runtime missing or crashed**: the catalog stays visible, installs are
  disabled, and an already-selected remote connection still answers.
- **No Vulkan loader**: `dlopen` fails, the backend is skipped silently, CPU
  runs.
- **A GPU exists and ggml cannot see it**: reported as `broken_install` rather
  than badged as a CPU-only machine. See **GPU status**.
- **Quantized KV without working flash attention**: `q8_0` requires it, and when
  the fused kernel is unavailable llama.cpp falls back to CPU attention silently,
  with the device near 0% utilisation. Both cache types are set together or
  neither, which removes the one trigger we control.
- **HF unreachable**: curated and installed render from the manifest and disk;
  search reports the destination is unavailable, which is a `503` naming the
  host, not an error dialog.
- **Header read truncated**: retry wider once, then fall back to a file-size
  estimate with the badge marked approximate.
- **A broken manifest**: the service substitutes an empty manifest rather than
  failing to start, so installed models and a local `.gguf` import still work.
- **An unreadable file in the models directory**: skipped with a warning when the
  preset is written. It costs that one model; failing would leave the runtime
  dead over a file nobody asked it to load.
- **`TOO_BIG`**: state the required and available bytes and name a smaller build.
  Never a bare disabled control.
- **Cancelled download**: the partial file stays as `.part`, the model is never
  discovered, and the next attempt resumes.
- **Dead curated pin**, where the repo or file 404s at download: say the model is
  no longer available from this source and fall through to the next-best entry.
  This has to be handled at runtime rather than checked at build time, because a
  repo can disappear between the release and a user's first install.

> **Three of these are the same failure wearing different clothes**, and the
> pattern is worth naming: llama.cpp degrades quietly and exits 0. The probe's
> backend search path, a missing backend dependency, and `-ngl` disabling the
> fitter all produce a working-looking system that is running on the CPU. Assume
> nothing worked until something says it did.

## Tests

2,661 unit tests pass across `tests/unit/llm` and `tests/unit/chat`. The ones
worth knowing about, because each encodes a failure that actually happened:

**Estimator**

- The two subtractions stay on their own sides: a profile where
  `need <= device_free` but `need > device_free - fit_reserve` asserts `PARTIAL`,
  which is the real RTX 3050 case and the one a collapsed `overhead` term gets
  backwards.
- `compute_buffers` is part of `need`: removing the term flips at least one
  fixture from `PARTIAL` to `FITS`.
- The Vulkan 4B measurement is not under-predicted, and a header stating no
  widths never prices scratch at zero.
- KV cells round up to the 256 boundary (16385 becomes 16640); the measured Qwen3
  numbers stay exact; a latent model prices one compressed head.
- A header's sliding-window period beats the built-in table; a per-layer array is
  exact; `shared_kv_layers` allocate nothing.
- `PARTIAL` is reachable on a unified budget and unreachable with no GPU;
  `can_install` is true for `PARTIAL` and false only for `TOO_BIG`.
- A property sweep over four shapes, five windows, two precisions and five budget
  shapes asserts that the items sum to the verdict's `need`, that weights do not
  move with the window, that KV and compute are non-decreasing in it, and that a
  `PARTIAL` fraction times the block count is an integer.

**Badge and recommendation**

- `test_badge_matches_the_load.py` sweeps every curated model against every
  budget shape and asserts a starred row's badge is never spill wording.
- A `PARTIAL` build below the light-spill ceiling is starrable, and a
  higher-ranked spilling build beats a fully resident lower-ranked one.
- `TOO_BIG` is refused regardless of rank: the tier relaxes residency, never
  physics.
- A CPU-only machine still gets a star.
- A quantized cache is allowed to rescue a larger model, because the star has to
  name the model the loader will actually run.

**Hardware**

- Device lines round-trip through a description containing a tab.
- The three GPU-status rows, plus integrated-only and OS-unknown.
- A probe raising `OSError` while the OS reports a card is `broken_install`.
- Two `ctypes` handles on Windows, one elsewhere.
- Two threads asking for the inventory produce exactly one probe call.

**Catalog and runtime**

- Curated renders with no network at all; search is `403` with egress off.
- A search row carries no `rank` field, asserted on the serialized response so it
  cannot be reintroduced silently.
- The committed architecture list equals what the staged `libllama` reports,
  skipped when no runtime is staged, so a pin bump that forgets the generator
  fails there rather than in a user's search results weeks later. A second check
  compares the recorded build against the pin in `fetch-llamacpp.mjs`, which
  needs no staged runtime and so covers the case where the first one skips.
- Every refusal reads as what the model is rather than naming its architecture,
  each kind of refusal reads differently, and an architecture llama.cpp has not
  merged yet blames the build rather than the file.
- A short read is refused rather than written: an empty gate would refuse every
  model on earth while looking like a considered answer.
- Every excluded architecture is one the runtime actually defines, which is what
  `granite-moe` failed for years without anyone being able to tell.
- Every key in the sliding-window table is a real architecture.
- A repo whose architecture is unsupported short-circuits with no `Range` request
  reaching the mock transport.
- A 500 on the resolve URL yields `approximate` builds rather than a failed repo.
- A projector file never gets its own preset section, and the model's section
  names it.
- The preset writes `fit-target = 1024`, or 1624 with a 600 MiB projector.
- A fake router covers health, models, props, load, tokenize, chat stream and
  delete; router mode against an empty models directory asserts
  `/props` reports `role: router`.
- Manifest: schema 3 is refused, a shape without `embedding_length` is refused,
  two `rank_basis` values are refused, and every shipped entry has positive
  widths.

**Migration**: a database seeded with an Ollama selection and an `ollama_pull`
egress row upgrades so the grant lands on `model_download` and `model_search` is
**not** created.

No new CI job. The build stays install, freeze, package, sign; neither llmfit nor
`huggingface.co` appears in it.

## Acceptance

- A clean machine on all three OSes opens the catalog with a hardware line and
  badged rows, with no scan button and no network.
- The recommended model installs and answers with citations.
- A model found through search, one Ollama's library never carried, installs and
  answers.
- A Windows machine with an RTX card runs on Vulkan from the installer alone, and
  the catalog prices against that card rather than the integrated GPU.
- Renaming `ggml-vulkan.dll` makes `/llm/system` report `broken_install`, the
  hardware line says the card was not detected, and no row reads *Reduced speed*.
  Restoring it returns `present`.
- A machine with no usable GPU runs on CPU with no error and still gets a star.
- Airgapped: curated install from a local `.gguf`, chat, and Studio all work.
- `/health` answers within a second of boot while `/llm/system` on a cold shader
  cache takes up to about 25 s.
- After an install, `models.ini` carries the planned `ctx-size` and
  `fit-target`, and the server log shows the fitter honouring the target.
- Quit leaves no orphan `surfsense-*` or `llama-server` process.

## What each machine gets

Computed from the shipped manifest through `build_budget`, `plan_load` and
`recommend`, in capacity mode. Cells are `state/offload fraction`.

| machine | resident | refusal | 0.6B | 1.7B | 4B | 8B | 14B | 32B | star |
|---|---|---|---|---|---|---|---|---|---|
| M2 8 GB | 4198 MiB | 6144 MiB | fits | fits | fits | 0.33 | too big | too big | 4B |
| RTX 3050 6 GB | 4210 MiB | 34046 MiB | fits | fits | fits | 0.33 | 0.60 | 0.81 | 4B |
| M4 16 GB | 9898 MiB | 14336 MiB | fits | fits | fits | fits | fits | too big | 14B |
| RTX 4070 12 GB | 9976 MiB | 40696 MiB | fits | fits | fits | fits | fits | 0.55 | 14B |
| RTX 4090 24 GB | 21976 MiB | 85464 MiB | fits | fits | fits | fits | fits | fits | 32B |
| M4 Max 64 GB | 48128 MiB | 63488 MiB | fits | fits | fits | fits | fits | fits | 32B |
| No GPU 16 GB | 14336 MiB | 14336 MiB | fits | fits | fits | fits | fits | too big | 14B |

Every machine gets a star, including the CPU-only one. Three gaps remain, and all
three are manifest work rather than estimator work:

1. **The top collapses.** 24 GB and 64 GB, 2.7x apart, get the same file. A
   higher quant does not fix it; 32B at Q8 is about 35 GB and still leaves room.
   The top needs a bigger model, and a mixture of experts is the right shape for
   those machines: large in memory but reading only a few billion parameters per
   token. `decode_fraction` is already computed and shipped for exactly that.
2. **A second variant on 8B and 32B**, say `Q6_K`, would fill the 16 GB band and
   give a 4090 somewhere to go. Two extra pins, not fifty, and `variants` is
   already a list.
3. **A vision entry.** All six are text-only, in an app with a PDF pipeline and
   an ingestion path that already accepts standalone images.

## Appendix: measurements

Taken against llama.cpp `b11050` (some earlier figures at `b11043`) and llmfit
`1.1.11`, on an M2 8 GB and on an RTX 3050 / Ryzen 5 9600X.

### Catalog scale

| Measurement | Value |
|---|---|
| GGUF repos on Hugging Face | 204,797 |
| Ollama library | 240 models |
| llmfit rows with an `ollama_name` | 138 of 9,590, 1.4% |
| llama.cpp `LLM_ARCH_*` names in the pinned build | 152, read from `libllama` itself |
| Of those, excluded as unable to chat | 21 |
| Architectures the install gate admits | 131 |
| GGUF repos with a useful pipeline tag | about 43,500, so roughly 80% have none |
| Top 40 GGUF repos carrying `base_model:quantized:` | 32 |
| GGUF header over HTTP Range | 1.79 MB, 2.5 s, for a 135M model |
| macOS DMG before the swap | 1,507 MB |
| `electron/ollama/` staged on macOS | 501 MB, of which 380 MB MLX |

### Device probing

| Measurement | Value |
|---|---|
| `ggml_backend_load_all()`, M2 | 2.3 ms |
| first `ggml_backend_dev_count()`, M2 (compiles 20 Metal libraries) | **19.0 s** cold, 43 to 49 ms warm |
| `ggml_backend_load_all()`, one backend | 77 ms Windows, 194 ms Linux |
| `ggml_backend_load_all()`, two backends | 205 ms |
| `ggml_backend_dev_memory()` first call, CUDA / Vulkan / CPU | 47.89 / 3.50 / 0.01 ms |
| `llama-server --list-devices` | 174 ms cold, 60 ms warm |
| CPU device, native Windows | 31884.6 MiB total, 22750.2 MiB free |
| CPU device, WSL2 | 26048.6 MiB total, 26048.6 MiB free, virtualised |
| CPU device, macOS | 8192.0 / 8192.0 MiB on a machine with about 2 GB free |
| M2 `recommendedMaxWorkingSetSize` | 5726.63 MB = 5461.3 MiB, which is MTL0's reported total |
| M2 devices listed | `MTL0` (GPU), `BLAS` (ACCEL, raw type 3), `CPU` |
| RTX 3050, `nvidia-smi` idle | 6144 MiB total, 5699 MiB free |
| RTX 3050, ggml after context init | 6143.5 MiB total, 5158 MiB free |
| Consumed before any weight loads | **986 MiB**, about 445 desktop and 541 context |

That last row is why the budget starts from ggml's `free` and not from a
nameplate total. `free` already excludes the desktop's allocation and the backend
context, so adding an overhead term on top charges the same memory twice.

### Fit terms

Qwen3 4B Q4_K_M at `-c 16384`, `--fit` on, RTX 3050 with 5,234 MiB free, from
llama.cpp's own allocation log:

| buffer | MiB |
|---|---|
| `Vulkan0` model | 2078.04 |
| `CPU_Mapped` model, spilled | 602.16 |
| `Vulkan0` KV | 1984.00 |
| `CPU` KV, spilled | 320.00 |
| `Vulkan0` compute | 143.62 |
| `Vulkan_Host` compute | 26.01 |
| `Vulkan_Host` output | 2.32 |
| **placed on device** | **4205.66** |
| **fit reserve, left unused** | **1028.34** |

Qwen3 1.7B Q4_K_M at `-c 16384` on the M2:

| buffer | MiB |
|---|---|
| `MTL0_Mapped` model | 1050.43 |
| `CPU_Mapped` model | 243.43 |
| `MTL0` KV | 1792.00 |
| `MTL0` compute | 102.24 |
| `CPU` compute | 24.01 |
| **the fitter's own projection** | **2944** |

`1050 + 1792 + 102 = 2944`, against `projected to use 2944 MiB`. The three-term
`need` is exact on Metal, as it was on Vulkan.

**243.43 MiB stayed on the CPU at "offloaded 29/29 layers to GPU".** The
non-repeating tensors are host-side even at full offload, so 29/29 does not mean
all weights on the device, and an offload fraction derived from the layer count
alone reads 0.00 while 19% of the file is elsewhere.

**Metal reports `0.00 MiB` buffer sizes during the fitter's probe pass**, before
the real load, so anything scraping buffer sizes must ignore the first pass.
`use shared buffers = true` also means Metal allocations are not the separate
arenas Vulkan and CUDA report.

### The estimator against those measurements

Current code, same shapes and windows:

| | KV predicted | KV measured | compute predicted | compute measured |
|---|---|---|---|---|
| 4B at 16384, Vulkan | 2304 MiB | 2304 MiB | 172 MiB | 170 MiB |
| 1.7B at 16384, Metal | 1792 MiB | 1792 MiB | 138 MiB | 126 MiB |
| 1.7B at 40960, Metal | 4480 MiB | 4480 MiB | 258 MiB | 246 MiB |

KV is exact. Compute is over in every case, which is the safe direction and the
reason the safety factor is 1.20.

> **One unexplained gap, recorded rather than smoothed.** The model buffers in
> both logs exceed the pinned file sizes: 2680 MiB against 2382 for the 4B, and
> 1294 MiB against 1056 for the 1.7B. The likeliest explanation is that the
> measured runs used a different publisher's build of the same quantization,
> since the logs name a quant but not a repo. It is worth re-measuring against
> the exact pinned file before concluding the weights term needs a correction,
> because if it does, it is a 12 to 22% under-estimate on the largest term.

### Offload and speed

Qwen3 4B Q4_K_M, `-ngl` controlling the fraction directly, f16 KV, `-p 512
-n 300`, Vulkan, RTX 3050:

| ngl | `f` | pp512 | tg300 |
|---|---|---|---|
| 99 | 0.00 | 1805.50 ± 1.75 | 52.45 ± 0.17 |
| 28 | 0.22 | 1454.68 ± 0.93 | 33.17 ± 0.25 |
| 18 | 0.50 | 1206.29 ± 9.86 | 19.85 ± 1.06 |
| 9 | 0.75 | 1027.97 ± 26.10 | 12.93 ± 0.43 |
| 0 | 1.00 | 907.43 ± 26.49 | 13.13 ± 0.67 |

`ngl 0` edging out `ngl 9` is real: splitting across devices costs transfers that
outweigh nine layers of device work.

The slowdown reduces to `1 / (f x r + 1 - f)` with `r = BW_gpu / BW_cpu`, and
every point fits `r` near 4 within ±20%. Cross-checked against absolutes: 131
GB/s effective on the device, 78% of the card's rating, against 33 GB/s on the
host, ratio 4.0. On a high-bandwidth card `r` is far larger, roughly 12 on a
4090, so the same fraction costs much more; and on unified memory `r` approaches
1 and spilling barely means anything. A threshold calibrated on a 3050 is
therefore not automatically conservative elsewhere.

### KV precision

The decisive result, `f16` KV at a 16K window on a 6 GB card:

```text
ggml_vulkan: Device memory allocation of size 316407808 failed.
ggml_vulkan: vk::Device::allocateMemory: ErrorOutOfDeviceMemory
llama_bench: error: failed to create context
```

`q8_0` at the same depth runs. On this class of card the planned configuration
does not fit, which is what makes cache precision an output of the fit
calculation rather than a global default.

Resident at depth 0: `f16` pp8192 1437.66 / tg300 52.47 against `q8_0` 1300.44 /
51.34.

> **That comparison is at the wrong depth and must not be quoted as q8_0's
> cost.** At depth 0 the cache is nearly empty, so its precision cannot matter.
> The valid comparison, `f16` at 16K depth, could not be taken because it fails
> to allocate on this card. What is known: `q8_0` at depth 16384 decodes at 27.46
> t/s against 51.34 at depth 0, and that halving is the cost of attending over a
> long context, not of quantizing it.

### Backend comparison

Qwen3 4B Q4_K_M, `-ngl 99`, same card:

| test | CUDA 13.4 | Vulkan | CUDA advantage |
|---|---|---|---|
| `pp512` | 1929.18 ± 8.84 | 1767.62 ± 1.43 | +9.1% |
| `pp8192` | 1537.12 ± 5.84 | 1394.77 ± 5.04 | +10.2% |
| `tg300` | 52.19 ± 0.22 | 51.13 ± 0.11 | +2.1% |

0.66 s on an 11 s turn, for 685 MB of payload. Full working in
[`08-cuda-backend.md`](08-cuda-backend.md).

### Why `rank` can be authored at all

This is the load-bearing fact under the whole authoring design. Qwen3 8B,
`--ram 64G` held fixed, sweeping the device budget:

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

Read the last four rows: four times the memory, and quality does not move. **It
stops moving the instant the quantization stops moving.** Hardware reaches
quality through exactly one channel, `best_quant`, and pinning the file closes
it. Confirmed across the population too: holding the quantization fixed over
2,424 models, quality differs in 0 of 2,424 and memory in 0 of 2,424.

Three consequences. `rank` is authored once and shipped frozen, because a number
that does not vary with the machine is data and a scan on the user's device has
nothing to discover. Only `score_components.quality` is read and `score` is
discarded, because `score` runs 65.1, 63.8, 63.6, 66.2, 63.6, 67.4 in the same
sweep, non-monotonic and moving with hardware since it blends fit and speed into
the quality term: the composite is a statement about a laptop, the component is a
statement about a file. And the declared budget must land llmfit on the pinned
quantization, which is why the authoring script sweeps the ladder and indexes it
rather than taking one reading.

### Router lifecycle

| Measurement | Value |
|---|---|
| Router up, three models discovered | VRAM unchanged from idle |
| Worker spawn argv | `--port 0 --model <path>` |
| Idle eviction without `--sleep-idle-seconds` | about 30 s |
| Model dropped into a running router's directory | still invisible after 26 s |
| Sidecar restart to pick up a preset change | 0.15 s |
| Grandchild reaping, `taskkill /T /F` | four processes, depth first, no survivors |
| `POST /models/load` with `{"args": ["-c","16384"]}` | ignored; worker used the model default |
| The same flag on the command line | honoured, `n_ctx_slot = 16384` |

### Device query against the advisor it replaced

| | llmfit | `ggml_backend_dev_memory()` |
|---|---|---|
| Memory budgeted | 8.0 GB | 5,461 MiB, the Metal working set |
| Context priced | 8,192 | the window we actually load |
| Qwen3 8B verdict | **Perfect** | **spills to system RAM** |

This is the failure the whole phase exists to delete: a confident label produced
from a memory figure that was not true on that machine.

## Open measurements and deferred work

Three things are deliberately left. Each needs a number nobody has taken rather
than code nobody has written.

### A quantized cache against a small spill

`plan_load` drops to `q8_0` whenever that turns a spill into residency. The
assumption underneath is that a resident model at `q8_0` beats a partly spilled
one at `f16`, and it has never been measured here. Published figures for
quantized caches report materially slower generation, which is evidence the
assumption can be wrong.

One model, one window, three configurations, on the two machines already used for
the rest of this phase:

| | cache | context | expected placement |
|---|---|---|---|
| A | `f16` | 16384 | spills; record `offloaded N/36` from the server log |
| B | `q8_0` with `flash-attn on` | 16384 | fully resident, 36/36 |
| C | `f16` | 8192 | fully resident, the control |

Qwen3 4B Q4_K_M, `parallel 1`, `fit-target 1024`. Three prompts of roughly 2K, 8K
and 14K grounding tokens, three runs each, median of `prompt_tokens_seconds` and
`predicted_tokens_seconds` from `/metrics`.

**The rule, fixed before the run so the result cannot be argued with.** If B
reaches 0.9x of A or better on the 8K prompt rate, the current preference stands.
If A matches or beats B, `plan_load` prefers a small `f16` spill below some layer
count, and only then does the policy change.

Note that the prompt rate decides this, not the decode rate, because this app is
prefill-dominated. Every published quantized-cache benchmark reports the decode
rate.

### The speed tier boundary

`LIGHT_SPILL` ends at 0.25, which currently excludes the configuration the
recommendation policy was originally written to allow. See the note under
**List order and the recommendation policy**. The measurement that settles it is
a prefill and decode pair for Qwen3 8B at its real offload fraction on the 3050,
against the 4B fully resident on the same machine, using the app's own prompt
shape rather than a synthetic one.

Whatever the answer, it moves one number in one module, and the badge and the
star move together by construction.

### Memory mapping policy

Some runtimes disable mmap on Metal when a load is predicted to spill, and on
Windows with CUDA by default. We pass neither and have measured neither. The
43-second paged load on an 8 GB Mac that motivated the unified pool rule is the
shape of failure this would address, but the pool rule removed the case that
produced it, so this is a curiosity rather than a known gap.

### Multimodal

Capabilities are read and `vision` is computed correctly, but nothing can send an
image yet: `Message.content` is still `str`, and there is no `ContentPart`. The
work is the seam widening to `str | tuple[ContentPart, ...]` with the adapter
downgrading for text-only models, plus `image_url.url` taking the local page path
Docling already writes, with no base64 round trip. The projector half is already
done: `projector.py` pairs the file, the preset names it, and `fit_target_mib()`
carries its bytes.

Ingestion accepts standalone images and PDF pages that are effectively pictures,
so a vision model has something to look at on day one. Audio and video are
deliberately not modelled, because nothing can feed them.

### Prompt tiers

69 prompt files remain, 23 cases across three tiers. After constrained decoding
and template capabilities, a tier carries reasoning depth only, not format
compliance, which plausibly collapses three tiers to two. Nothing measures that
today; the internal eval described under **Ranking** is what would.

## References

- [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), router mode, `/models`, `/props`, `/tokenize`
- `common/fit.cpp` and `common/common.h`, the fitter's search and `fit_params_target`
- `src/llama-kv-cache-iswa.cpp`, sliding-window cell sizing
- `src/llama-model.cpp::load_swa_pattern`, the per-architecture window patterns
- [`ggml-backend-reg.cpp`](https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-backend-reg.cpp), `ggml_backend_load_best()` and the silent skip on `dlopen` failure
- [`common/jinja/caps.h`](https://github.com/ggml-org/llama.cpp/blob/master/common/jinja/caps.h), `chat_template_caps` fields
- [llama.cpp#19980](https://github.com/ggml-org/llama.cpp/issues/19980), `--fit` does not account for projector memory
- [llama.cpp#29006](https://github.com/ggml-org/llama.cpp/issues/29006), `json_schema` returning 400 on some templates
- `gguf-py/gguf/{gguf_reader,constants}.py`, the pinned parser and its key table
