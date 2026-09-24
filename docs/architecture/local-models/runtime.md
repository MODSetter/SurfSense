# The llama.cpp runtime

Local generation runs in one `llama-server` process in router mode, which
Electron starts beside the API and restarts whenever the API rewrites its preset
file. llama.cpp owns layer placement and model lifecycle; SurfSense owns
everything around them: which files sit in the models directory, the launch
arguments each model gets, and every byte downloaded from Hugging Face. The
shaping rule is to assume nothing worked until something says it did, because
llama.cpp's common failures exit 0 and look like success.

**Code:** [`surfsense_local/backend/modules/llm/providers/llamacpp/`](../../../surfsense_local/backend/modules/llm/providers/llamacpp/), [`surfsense_local/electron/src/main/sidecars/llamacpp.ts`](../../../surfsense_local/electron/src/main/sidecars/llamacpp.ts), [`surfsense_local/electron/src/main/index.ts`](../../../surfsense_local/electron/src/main/index.ts) (preset watcher), [`surfsense_local/electron/scripts/fetch-llamacpp.mjs`](../../../surfsense_local/electron/scripts/fetch-llamacpp.mjs)
**Decisions:** [ADR 0011](../../adr/0011-llama-cpp-local-runtime.md), [ADR 0012](../../adr/0012-vulkan-only-gpu-backend.md), [ADR 0015](../../adr/0015-openai-compatible-connections.md)

How each model's window and cache precision are chosen is in
[`fit.md`](fit.md); how models reach the directory is in
[`catalog.md`](catalog.md).

## Why llama.cpp replaced Ollama

Ollama's library held 240 models. A measured scan resolved 138 of 9,590 llmfit
rows to an installable Ollama artifact, 1.4%, and dropped roughly 1,500 models
per scan that llama.cpp could run directly from a Hugging Face GGUF. llama.cpp
runs anything in GGUF, 204,797 repos on Hugging Face, bounded only by the
architectures it supports. It also ships smaller (11 to 31 MB against Ollama's
501 MB staged payload), fits a model to the machine itself (`--fit`, on by
default), and exposes structured-output and multimodal contracts that Ollama's
native API did not.

## Router mode

`llama-server` starts in one of two shapes. Given `-m <path>` it loads that model
and serves it. Given `--models-dir <dir>` and no `-m` it starts as a router: it
holds no model, lists every GGUF in the directory as `unloaded`, and spawns a
worker process per model when one loads. Both shapes answer `/health`
identically, so `RouterClient.is_router()` checks that `GET /props` reports
`"role": "router"`.

Router mode is what lets the sidecar boot on a clean machine. Measured at
`b11050` on Windows and Linux, `/health` returns `{"status":"ok"}` and `/models`
returns `{"data":[],"object":"list"}` against an empty directory. A router with
three models discovered leaves VRAM unchanged from idle, in the plan's router
lifecycle measurements, which do not record the platform. The directory itself
must exist: a comment in `electron/src/main/index.ts` records that `llama-server`
exits 1 when `--models-dir` does not exist, so Electron creates it before the
first start.

The cost is that per-model arguments cannot be sent at load time. Measured on
macOS at `b11050`, `POST /models/load` with `{"args": ["-c","4096"]}`,
`{"args": ["--ctx-size","4096","-fa","on"]}` or `{"preset": "..."}` returns
`200 {"success":true}` while the spawned worker's argv stays byte identical; the
same flag passed on the command line is honoured. The router reports each
worker's real argv under `GET /models` as `status.args` (`RouterModel.args`),
which is the only reliable way to see what it did.

`--models-preset PATH` is the mechanism that works, and the router reads the file
once, at startup. A model dropped into a running router's directory is still
invisible 26 seconds later and appears immediately after a restart. So
installing a model, deleting one, or changing a model's load plan means
rewriting the preset and restarting the sidecar. A restart of an idle router
costs 0.15 s; one holding the selected model also throws that model away, and
reloading it costs the 10 to 26 s the warming below exists to hide.

## Sidecar flags

`llamacppSpec()` in `electron/src/main/sidecars/llamacpp.ts` starts:

```text
llama-server
  --models-dir <dataDir>/models
  --host 127.0.0.1  --port <free port>
  --models-max 1
  --models-autoload
  --no-ui
  --jinja
  --reasoning-format deepseek
  --models-preset <dataDir>/models/models.ini      only once the file exists
```

with `cwd` set to the binaries directory and `LLAMA_CACHE` pointed at the models
directory.

- `--models-max 1`, because the app asks one question at a time and a second
  resident model is memory taken from the one in use.
- **No `--sleep-idle-seconds`.** It defaults to `-1`, so a loaded model is never
  unloaded on a timer, and the router's only other eviction, LRU under capacity
  pressure, cannot happen with one model and `--models-max 1`. Re-measured at
  `b11050` on Metal and on Vulkan, a model left idle for over a minute reports
  `loaded` throughout. Passing the flag is what would unload a model
  mid-conversation, and the reload costs the full 10 to 26 s, because sleeping
  frees the model and its context rather than parking them. An earlier
  measurement recorded a self-eviction after about 30 s without the flag; it did
  not reproduce on either backend and was withdrawn. The cost is that a local
  model, once loaded, stays resident while the app runs, even after the user
  switches to a remote connection: nothing calls `RouterClient.unload()`.
  Someone who never loads a local model spends none of it, because the router
  holds no device memory until something loads.
- `--models-autoload` is the upstream default, stated because the chat path
  depends on it. The router's proxy calls `ensure_model_ready` before
  forwarding, so a cold model loads on the request that needs it, and nothing on
  the chat path calls `POST /models/load`. Asking as well was a check-then-act
  across a socket: it lost the race to the request already loading the model,
  and the router's `400 model is already running` took out title generation on
  every new thread. `RouterClient.load()` is used only by the warm up described
  under [warming](#warming-listed-is-not-loaded), and treats that 400 as success.
- `--no-ui`, because llama-server ships its own web UI, which the app neither
  needs nor wants exposed.
- `--reasoning-format deepseek` routes `<think>` blocks to
  `message.reasoning_content`. Without it a thinking model's trace enters the
  answer, and citation rewriting corrupts `[n]` tokens that appeared inside the
  reasoning.
- `cwd` is the binaries directory because ggml scans the running executable's
  own directory for backend libraries. Anywhere else it reports no devices,
  silently, and every model runs on the CPU.
- The preset flag is conditional because the router rejects a missing preset
  file, and on a clean install nothing has written one yet.

Electron hands the same locations to the Python sidecars as
`SURFSENSE_LOCAL_LLAMACPP_BASE_URL`, `SURFSENSE_LOCAL_LLAMACPP_MODELS_DIR` and
`SURFSENSE_LOCAL_LLAMACPP_LIBRARY_DIR`; the last is where the API loads ggml to
probe the hardware ([`fit.md`](fit.md)). The sidecar
runs in development too, from `electron/llamacpp/`, which `predev` fills: a pinned
build has to be started by the app in both modes, or development tests a version
the app never ships. When the binary is not staged the sidecar does not start.
Boot waits only on the API's health; the runtime's state shows through
`GET /llm/providers`.

`watchGenerationPreset()` in `electron/src/main/index.ts` polls the preset's size
and mtime every 5 s and restarts the sidecar on a change, the same shape as
`watchImageModel()` for sd-server: the API is the authority, and a change is
user-initiated and rare.

## Never set a layer count

```text
common_fit_params: failed to fit params to free device memory:
                   n_gpu_layers already set by user to 99, abort
```

Measured at `b11050`: with `-ngl 99` the model then loaded entirely on the CPU,
478 MiB of VRAM touched on a machine with a working RTX 3050, no error, exit 0.
It looks like it worked. `-ngl 99` reads as "use the GPU harder", which makes
this the easiest silent failure to introduce by accident, so the preset writes no
layer count and `render_presets()`'s docstring says so where someone would go to
add one.

`--fit` searches rather than solves, reloading at each step. Measured at
`-c 40960` against a 5,460 MiB working set:

```text
29/29 layers → 0/29 → 29/29 → 22/29 → 23/29      settles at 23/29
```

It never touched the context, because `-c` was set and the fitter treats an
explicit value as fixed. Left unset, it reduces context on its own as far as
`fit_params_min_ctx`, 4096, which is below the app's 8,192 floor and happens
silently. So every preset section writes `ctx-size`: leaving it out hands the
floor to llama.cpp.

## The preset file

`providers/llamacpp/preset.py` renders one section per model, keyed by the id the
router reports, which is the filename stem:

```ini
[Qwen3-8B-Q4_K_M]
model = /Users/…/models/Qwen3-8B-Q4_K_M.gguf
ctx-size = 16384
parallel = 1
fit-target = 1024
fit-ctx = 16384
mmproj = /Users/…/models/mmproj-Qwen3-8B-Q4_K_M.gguf ; only with a projector
cache-type-k = q8_0                            ; only at q8_0
cache-type-v = q8_0
flash-attn = on
```

- `parallel = 1`. llama-server defaults to four slots, which sizes the KV cache
  for concurrency this app never uses.
- `fit-target` is pinned rather than inherited. The badge subtracted a specific
  margin, 1 GiB, so passing it makes the two agree by construction. A vision
  projector's bytes are added to it, because `--fit` allocates the projector
  after placing layers and does not count it while deciding
  ([llama.cpp#19980](https://github.com/ggml-org/llama.cpp/issues/19980)); a
  600 MiB projector gives `fit-target = 1624`.
- `fit-ctx` is inert while `ctx-size` is set, since llama.cpp only shrinks a
  context it chose itself. It is written anyway, so a later change to how the
  window is set cannot quietly hand the floor back to llama.cpp's 4096.
- The `q8_0` lines are written as a group. Set one cache type without the other
  and the fused flash-attention kernel is skipped, after which attention falls
  back to the CPU silently. An `f16` plan writes none of them.

The file is `models.ini` in the models directory, named once on each side
(`PRESET_FILE`). `write_presets()` writes a sibling `.tmp` and renames it, so a
half-written INI never loads.

## From download to answerable

llama.cpp's catalog engine, `LlamaCppEngine.reprice()` ([`models_folder/preset.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/models_folder/preset.py)), writes the preset for every `.gguf` in the models
directory, at API startup (on the warm thread, after the device probe), after
every install and after every delete. At startup, because a model placed in the
directory by hand would otherwise load at llama.cpp's default window, and a stale
section would keep advertising a model whose file is gone; after a delete,
because the router serves a stale section as a real entry (`source: preset`) that
fails when chosen.

For each file it reads the header and skips anything the header does not name a
model, such as a vision projector, which has a header and a size like any model.
It skips an unreadable file with a warning: a truncated or foreign file costs that
one model, while failing would leave the runtime dead over a file nobody asked it
to load. It pairs each model with the projector its install record names, or one saved
as `mmproj-<model>.gguf`, and only when that projector's header says it sees
images and is as wide as the model, or either header leaves the width out;
nothing is paired by guessing from the
folder. It plans the
load with `plan_load()` ([`fit.md`](fit.md)): the capacity budget decides the
verdict, so the plan agrees with the badge the catalog showed, and the live
budget caps how far the window widens past the floor.

The install stream then waits. `wait_until_servable()` polls the router's
`/models` for up to 30 s at 0.5 s intervals, because the router learns about a
new model only by restarting, and reporting the install complete before then
tells the user a model is ready while a chat returns `model '<id>' not found`, a
400. A timeout returns `False` rather than raising, and the stream completes with
"Downloaded. It becomes available once the runtime restarts.": the download
succeeded and the file is on disk, so reporting a failed install would be wrong.

### Warming: listed is not loaded

`wait_until_servable()` answers whether the router knows about a file, not
whether its weights are in memory. A model that is merely listed still pays a
full load on the first question asked of it, 10 to 26 s of silence measured on an
M2 (commit 865eb37b1). So the API loads the model at the three moments it knows one is about to be
wanted and nobody is waiting yet:

- **During an install**, once the router lists the file. `warm_model()` starts
  `POST /models/load` and watches `GET /models/sse`, because the load call
  blocks until the model is resident and says nothing on the way, while the event
  stream reports every stage but never asks for anything. The stream's named
  stage and 0-to-1 progress go out as the install's `preparing` frames
  ([`catalog.md`](catalog.md)). Frames for any other model are ignored: with
  `--models-max 1`, another model's load is this one being evicted.
- **On selection**, as a FastAPI background task after
  `PUT /llm/selection/{model_type}` has answered, because the load blocks until the
  model is resident ([`selection.md`](selection.md)).
- **At startup**, on the catalog warm thread after `reprice()`, because the
  preset decides the window the load will use. Nothing is resident after a
  restart. `reprice()` always rewrites the preset, though, and Electron restarts
  the sidecar on any rewrite within 5 seconds, so this load most likely lands on
  a router that is about to be replaced (Known gaps).

`residency.warm_selected()` gates the last two on the selection's provider being
`llamacpp`, so choosing a remote model, or starting up with one selected, loads
nothing. It does not unload a local model loaded earlier; that one stays
resident until the sidecar restarts. No warm raises: one that fails costs the wait it was trying to
avoid, which is where the caller already was, and a watch cut short by the
sidecar restarting for a preset rewrite leaves the model to load on demand.

## Turning thinking off

A thinking model emits its whole trace before its first answer token, so a call
with a small `max_tokens` returns nothing. Measured against Qwen3 1.7B at
`b11050`, a 12-token title request came back with `content: ''`,
`finish_reason: length`, and a full `reasoning_content`.

A caller that wants no reasoning passes `reasoning=False`; title generation is
the one that does. The chat provider then adds `THINKING_OFF`, two fields
defined in `thinking.py`, to that one request,
because each covers the other's blind spot and both were measured to work:

```python
THINKING_OFF = {
    "thinking_budget_tokens": 0,
    "chat_template_kwargs": {"enable_thinking": False},
}
```

`chat_template_kwargs` is the documented mechanism and is inert on a model whose
template never reads `enable_thinking`. `thinking_budget_tokens` is llama.cpp's
own end-of-thinking injection, so it holds whatever the template does.

Two alternatives were measured and rejected. `reasoning_budget` as a request
field is accepted and ignored, which looks like it worked. `--reasoning-budget 0`
on the command line applies to the whole router, and setting it at all makes the
server ignore `thinking_budget_tokens`, whose handler runs only while the flag is
at its `-1` default. The sidecar never passes it.

## The provider

`LlamaCppProvider` satisfies the same `Generator` protocol as a remote endpoint,
so resolution sees a provider named `llamacpp` and nothing else about the
runtime. The catalog and the selection route do drive the router directly:
downloads, the preset, waiting for the router to list a model, and warming.

| Need | How |
|---|---|
| Is it up | `GET /health` |
| What is installed | `GET /models`: every file in the models directory, resident or not; the provider drops a file whose header says it is not a model |
| Template capabilities and the loaded window | `GET /props?model=<id>` (`chat_template_caps`, `default_generation_settings.n_ctx`), plus `architecture.input_modalities` from `GET /models` |
| Exact token counts | `POST /tokenize`, proxied to the model's worker, which autoloads it |
| Chat | `POST /v1/chat/completions`, through `OpenAICompatibleChatProvider` |
| Download | SurfSense fetches `resolve/{revision}/{path}` itself and checks each file against its sha256 when it has one ([`catalog.md`](catalog.md)) |
| Delete | SurfSense unlinks every file the install record names ([`catalog.md`](catalog.md)) |

Chat is composed, not reimplemented. llama-server speaks OpenAI on
`/v1/chat/completions`, so the streaming, deadlines, error handling and message
shaping in `OpenAICompatibleChatProvider` work against it unchanged. The one
addition is a fallback:
[llama.cpp#29006](https://github.com/ggml-org/llama.cpp/issues/29006) returns 400
for `json_schema` on some templates, and on that 400 the provider retries once
unconstrained, because losing a whole Studio format to a template quirk is worse
than an answer the parser can still repair. Before sending, `for_template()`
folds the system prompt into the first non-system turn for a template with no
system role ([`selection.md`](selection.md)).

There is no `pull()`. Fetching weights by name made sense when the runtime owned
the download; here SurfSense fetches the GGUF itself, because an in-process fetch
is the only place `egress.require()` can hold, and it buys resume as well.

Delete unlinks the file rather than calling `DELETE /models`. The router only
removes what it downloaded into its own cache and refuses everything else:
measured, `model name=… is not removable (not from cache)`, a 500, with the file
left on disk. Everything SurfSense installs lands in `--models-dir`, so that call
can never succeed for it.

`/props` is read once per model rather than once per message, cached by model id:
before the cache, `context_tokens()` and `chat()` each made their own round trip
every turn. Nothing invalidates the cache and nothing needs to, because
`get_provider()` builds a fresh adapter per call, so an entry cannot outlive the
resolution that created it, let alone the sidecar restart a preset rewrite
causes.

## The Mac path

Dropping Ollama costs Apple Silicon speed on models under roughly 14B, and MLX
does not ship: MLX's format covers 23,985 Hugging Face repos against GGUF's
204,797, and one format with the full catalog wins. The escape hatch already
ships and does not leave the machine. The connection form offers
`LM Studio (local)` (`http://localhost:1234/v1`) and `Ollama (local)`
(`http://localhost:11434/v1`) presets, and LM Studio runs MLX on Apple Silicon.

- `host_destination()` returns `None` for a loopback host, so `egress.require()`
  no-ops and no egress prompt appears.
- `api_key_ciphertext` is nullable and a connection with no key sends no
  `Authorization` header, so keyless local endpoints work end to end.

The Ollama preset is kept deliberately. It is the user-managed MLX path now, not
dead code, and one of the few places the string `ollama` legitimately survives.
Connections are described in [`../connections.md`](../connections.md).

## Packaging

`fetch-llamacpp.mjs` pins one llama.cpp build, `b11050`, and a SHA-256 per
target, and never fetches a floating tag: llama.cpp publishes about ten builds a
day with no stable channel.

| Target | Asset | Size |
|---|---|---|
| darwin-arm64 | `llama-b11050-bin-macos-arm64.tar.gz` | 11.2 MB |
| win32-x64 | `llama-b11050-bin-win-vulkan-x64.zip` | 31.8 MB |
| linux-x64 | `llama-b11050-bin-ubuntu-vulkan-x64.tar.gz` | 30.4 MB |

The GPU backend is Vulkan on every platform off Apple Silicon, and
`checkConfiguration()` refuses any other asset for Windows or Linux; no CUDA
payload ships. Vulkan covers NVIDIA, AMD and Intel from one archive, and its
loader ships with Windows. Adding CUDA would be a packaging change with no code
change, because ggml selects a backend by the files present; the measurement that
decides it is in [`../../proposals/cuda-backend.md`](../../proposals/cuda-backend.md).
The Vulkan archive is the CPU archive plus one file, and every CPU
micro-architecture variant ships inside it: 15 on Windows, 10 on Linux.

Staging, in order:

1. Download the asset and check its SHA-256.
2. Keep `llama-server` and the libraries it links, and drop the other tools'
   libraries: the archives carry 24 executables and the app runs one, which also
   shrinks the macOS notarization surface. On macOS and Linux the library
   symlink chains are recreated rather than dereferenced, because the runtime
   loads by the name in the link.
3. Keep the upstream `LICENSE`.
4. Run `llama-server --list-devices` from the stage directory, and fail unless it
   lists devices or says it found none.
5. Swap the stage into `electron/llamacpp/`, which electron-builder copies
   verbatim to `resources/llamacpp/`.

SurfSense ships no generation weights: model licences are not permission to
redistribute them, so the app downloads the file its manifest pins, or one the
user finds by search, into the writable data directory. Rules for the packaged
runtime:

- Code signing and notarization must cover `llama-server` and its libraries. The
  router spawns a worker per model, so the macOS hardened runtime has to hold for
  a grandchild process as well as the sidecar; `electron-builder.yml` sets
  `entitlementsInherit`.
- The release workflow pins `ubuntu-22.04`. `ubuntu-latest` migrates and would
  silently raise the AppImage's glibc floor; the Vulkan build needs 2.34.
- On Windows, `vulkan-1.dll` is in `System32` on a stock install, so nothing is
  bundled for it.
- Quitting reaps the whole tree. On Windows the supervisor runs
  `taskkill /pid <pid> /t /f`, which walks the router's children; verified at
  `b11050` with a model resident, it terminated four processes depth first with
  no survivors. On macOS and Linux each sidecar is spawned in its own process
  group, which receives `SIGTERM` and then `SIGKILL` after 5 s.
- `bundling/api.spec` ships `modules/llm/catalog/local/manifest/models.json` at
  `modules/llm/catalog/local/manifest`. The manifest is read by path, so the analyser cannot see
  it, and a packaging test asserts it is bundled.
- Release CI stages the runtime with `node scripts/fetch-llamacpp.mjs`, and on
  Linux runs the packaged `llama-server --list-devices` from
  `resources/llamacpp/`.

The rest of the installer is in [`../packaging.md`](../packaging.md).

## Failure behavior

- **Runtime missing or crashed.** The catalog still renders, because it comes
  from the manifest and the disk. A selected remote connection still answers,
  because resolving it never touches the sidecar. An install still downloads and
  ends with "Downloaded. It becomes available once the runtime restarts."
- **No Vulkan loader.** `dlopen` fails, ggml skips the backend silently, and the
  CPU runs.
- **A GPU exists and ggml cannot see it.** Reported as `broken_install` rather
  than badged as a CPU-only machine ([`fit.md`](fit.md)).
- **A quantized cache without a working flash-attention kernel.** llama.cpp falls
  back to CPU attention silently, with the device near 0% utilisation. Both cache
  types are set together or neither, which removes the one trigger the app
  controls.
- **The local runtime answers a chat with a 500.** That is llama-server saying it
  could not load the file: an architecture this build cannot build, or builds and
  then aborts on. Chat reports `MODEL_CANNOT_RUN`, "SurfSense cannot run this
  model. Pick another model.", not advice to retry.
- **Hugging Face unreachable.** Search returns a 503 naming the host; curated and
  installed rows are unaffected.
- **A broken manifest.** The catalog substitutes an empty one rather than failing
  to start, so installed models still work.
- **An unreadable file in the models directory.** Skipped with a warning when the
  preset is written.
- **A cancelled download.** The partial file stays as `.part`, the router never
  discovers it, and the next attempt resumes with a `Range` request. A server
  that ignores the range, answering without a `206`, has the held bytes discarded
  rather than appended to.

The probe's backend search path, a missing backend dependency and `-ngl`
disabling the fitter are one failure in different clothes: each produces a
working-looking system running on the CPU, with exit 0. That is why the working
directory, the GPU status check and the absent layer count are each held by a
test.

## How it is tested

Unit tests in
[`surfsense_local/backend/tests/unit/llm/providers/llamacpp/`](../../../surfsense_local/backend/tests/unit/llm/providers/llamacpp/)
run the provider against a fake router. [`surfsense_local/electron/src/main/sidecars/llamacpp.test.ts`](../../../surfsense_local/electron/src/main/sidecars/llamacpp.test.ts)
holds the sidecar's working directory, `--models-autoload`, and the absence of a
layer count, of `--reasoning-budget` and of `--sleep-idle-seconds`.

## Known gaps

- The Linux `.deb` declares no dependency on the Vulkan loader (`electron-builder.yml` has no `deb` section), though `libggml-vulkan.so` needs `libvulkan.so.1` from the host; without it the app runs on the CPU.
- The startup warm most likely loads into a router that is about to restart: `reprice()` rewrites the preset on every start, `watchGenerationPreset()` starts watching before the API is healthy and restarts the sidecar within 5 seconds of the rewrite, and `warm_selected()` sends the load straight after `reprice()` returns. This is from reading the code, not a measurement.
- Release CI runs the packaged `llama-server --list-devices` on Linux only; the macOS and Windows builds are checked only in the staging directory by `fetch-llamacpp.mjs`.
