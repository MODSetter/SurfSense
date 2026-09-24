# Fit: pricing a model against this machine

Every local build on the model screen carries a fit verdict: it runs at full
speed, it runs with part of it on the CPU, or it cannot run here. The verdict is
subtraction rather than judgement: what the model allocates, read from its GGUF
header, against the one device and the host memory that ggml's own allocator
reports. It is advisory, because `--fit` places the layers at load and
generation is ground truth after that, so every unknown rounds up. An
over-estimate costs a pessimistic badge on a model that installs anyway; an
under-estimate ships a confident badge about a model that spills, which is the
failure the estimator exists to prevent.

**Code:** [`surfsense_local/backend/modules/llm/gguf/`](../../../surfsense_local/backend/modules/llm/gguf/), [`surfsense_local/backend/modules/llm/hardware/`](../../../surfsense_local/backend/modules/llm/hardware/), [`surfsense_local/backend/modules/llm/fit/`](../../../surfsense_local/backend/modules/llm/fit/), [`surfsense_local/backend/modules/chat/budget.py`](../../../surfsense_local/backend/modules/chat/budget.py)
**Decisions:** [ADR 0013](../../adr/0013-fit-from-the-allocator.md), [ADR 0012](../../adr/0012-vulkan-only-gpu-backend.md)

The catalog that shows these verdicts is [`catalog.md`](catalog.md); the preset
that carries the load plan to llama.cpp is [`runtime.md`](runtime.md).

```text
  hardware ─── probe_devices()   child process, ggml's own device list
     │             └─ gpu_status: present | absent | broken_install | unknown
  budget ───── build_budget(devices, ram)   one device, never a sum
     │             resident_bytes   what must hold the model for full speed
     │             refusal_bytes    what physics allows at all
  model ────── GGUF header, local file or HTTP Range on huggingface.co
     │             ModelShape: 22 fields, quantization independent
     ▼
  estimate ─── itemise() -> weights + mmproj + KV(window) + compute
     │         FITS | PARTIAL | TOO_BIG, plus an offload fraction in layers
     │             └─ speed_tier() ─┬─ badge()               what the row says
     │                              └─ RECOMMENDABLE_TIERS   whether it can be starred
     ▼
  plan_load() ── window and cache precision, written to models.ini
     ▼
  llama-server ── --fit places the layers. That is the real answer.
```

## Reading a model

### The parser

`gguf==0.19.0`, llama.cpp's own `gguf-py` package, pinned exactly in
`pyproject.toml`. It is upstream's parser for two reasons: the search tier parses
bytes from arbitrary Hugging Face repositories, the one path where a malformed
file is adversarial rather than unlucky, and upstream's parser is the one that
receives hardening; and metadata key names come from `gguf.constants.Keys`, so a
rename upstream is an import error rather than a field that silently reads zero.

### Reading a header out of a prefix

`GGUFReader` memory-maps a path, and its constructor walks the tensor table,
slicing each tensor's data at an offset inside the weights. A prefix has no
weights, and numpy shortens a slice that runs past the end rather than raising,
so a short read would surface later as a confidently wrong shape instead of a
retry. `gguf/header_prefix.py` is the adapter: it writes the prefix to a
temporary file for the reader to map, and overrides three private methods.

- `_get` bounds-checks every read and raises `TruncatedHeaderError` when the
  prefix is short.
- `_build_fields` keeps only the length of an array past 4,096 items
  (`ElidedArray`), so a vocabulary is counted rather than decoded.
- `_build_tensors` keeps names, dimensions and raw type ids without touching data.

`TruncatedHeaderError` subclasses `ValueError` on purpose: a caller that can widen
the read catches it by name and retries, while a caller that only needs to skip an
unusable file catches `ValueError` and gets both this and a file that was never a
GGUF. Because the overridden methods are private upstream, `test_header_prefix.py`
asserts the installed version is `0.19.0` beside the three behaviours, so a bump
cannot pass silently. The reader closes its memory map explicitly, because
Windows refuses to unlink a mapped file and this runs once per searched model.

### Where header bytes come from

`gguf/source.py` reads a local file or the front of a remote one. Hugging Face
serves `Range` requests on model files (measured: a `206` with
`accept-ranges: bytes`), so a model can be priced before a single weight is
downloaded. Header size scales with vocabulary, not with model size: a 135M
model's metadata ends at 1.77 MB, while Qwen3-Coder-30B-A3B's runs to 5.94 MB
with 579 tensor entries after it. No single prefix suits every model, so the read
widens from `PROBE_BYTES` (256 KiB) to 8 MiB to 24 MiB.

The first step is deliberately far too small for a chat model. A file that is not
one (a projector, an imatrix, a diffusion GGUF) carries no tokenizer, so its
metadata ends inside the probe and the catalog can refuse it for the cost of
256 KiB ([`catalog.md`](catalog.md)). A chat model truncates there and widens. A
header still truncated at 24 MiB raises.

### `ModelShape`

Twenty-two fields, named after the GGUF metadata keys they come from, and
quantization independent: measured, the architecture fields are identical across
`Q4_K_M`, `Q8_0` and `f16` of the same model, so one header read prices every
build of it. Seven are required. The rest default to zero, and each one only ever
sharpens an estimate, with absence being the conservative answer rather than a
zero cost.

| Group | Fields |
|---|---|
| Required | `architecture`, `block_count`, `head_count_kv`, `key_length`, `value_length`, `context_length`, `n_vocab` |
| Graph width | `embedding_length`, `feed_forward_length`, `expert_feed_forward_length`, `expert_shared_feed_forward_length`, `expert_used_count`, `expert_count` |
| Sliding window | `sliding_window`, `sliding_window_pattern`, `sliding_window_layers`, `key_length_swa`, `value_length_swa`, `shared_kv_layers` |
| Per layer | `head_count_kv_layers` |
| Latent attention | `kv_lora_rank`, `key_length_mla` |

Two reading rules in `gguf/shape.py` are worth knowing. A field that is scalar in
most models and per-layer in some is reduced with `_widest()` where one number is
wanted, because the widest layer answers how large one layer can be and taking
the first element would under-state a hybrid. The KV head count also keeps its
per-layer values, in `head_count_kv_layers`, because the cache is a sum over
layers rather than the widest layer times a count. Older headers that omit the
per-head lengths have them implied from `embedding_length // head_count`.

## Reading the machine

### The probe runs out of process

`probe_devices()` in `hardware/probe_subprocess.py` spawns a child to ask ggml
what the machine has; the in-process path survives only as a fallback. Three
measured reasons, each sufficient alone:

- **The backend scan keys on the running executable's directory.**
  `ggml_backend_load_all()` discovers backends in the directory of the running
  executable, not the one the libraries were loaded from. On a Windows machine
  with a working RTX 3050, the same probe found 0 devices run from elsewhere and
  2 (`Vulkan0` and `CPU`) run from the llama.cpp directory. Loading by absolute
  path does not help, and `GGML_BACKEND_PATH` expects a file: given a directory it
  logs `load_backend: failed to load <dir>` and leaves the count at zero. In
  process this meant a global `chdir` under a lock inside a server handling other
  requests; in a child it is just the working directory.
- **The first Metal device query compiles 20 shader libraries.** On an M2,
  `ggml_backend_load_all()` takes 2.3 ms and the compile happens inside the first
  `ggml_backend_dev_count()`, at 19.0 s cold and 43 to 49 ms warm.
  `LocalCatalogService.warm()` enumerates the devices on a daemon thread at API
  startup, so `/health` does not wait on it, and a request arriving meanwhile
  waits on the same lock instead of starting a second probe.
- **A GPU driver that faults takes its process with it.** A child is a probe that
  failed. The API process is the application.

The child prints one tab-separated line per device (name, description, type,
total bytes, free bytes). The format is plain because ggml logs to stdout on some backends; a line that
does not parse is skipped as a likely log line. A non-zero exit or a timeout
(90 s, bounding the Metal compile) logs a warning and falls back in process. The
frozen API re-executes itself behind `--probe-devices` (`main.py`); in
development the child is `python -m modules.llm.hardware.probe_script`. The
library directory is made absolute before it is handed over, because the child
starts in that directory and a relative path would find nothing there and fall
back in process, silently.

The exported symbols are split: `ggml` exports `ggml_backend_load_all`,
`ggml_backend_dev_count` and `ggml_backend_dev_get`, while `ggml-base` exports the
device's name, description, type and memory. ELF and Mach-O resolve the second
library through their own dependency records, so one handle on `libggml` works.
PE exports do not chain, so Windows needs both handles: `ggml.dll` alone raises
`AttributeError: function 'ggml_backend_dev_name' not found`, an error at startup
rather than a wrong answer.

### Device selection

A machine reports one entry per backend and device pair. Measured on the Windows
test machine:

```text
[0] Vulkan0  type=GPU    6002.0 MiB total, 5234.0 MiB free   NVIDIA GeForce RTX 3050
[1] Vulkan1  type=ACCEL 16198.3 MiB total                    AMD Radeon(TM) Graphics
[2] CPU      type=CPU   31884.6 MiB total, 22750.2 MiB free  AMD Ryzen 5 9600X
```

`select_device()` takes the first device typed `GPU`, or `None`.

- **First, not largest.** Sorting by memory picks the 16 GB integrated part over
  the 6 GB discrete card and places every layer on the slower device. ggml
  already orders backends by preference, so taking the first is also backend
  selection.
- **Never a sum.** One device is the budget. The same card listed under two
  backends would otherwise turn a 6 GB card into 12 GB.
- **An integrated GPU is not a GPU for budgeting.** A part carving from system
  RAM has no memory of its own to place layers in. `IGPU` and `ACCEL` both fail
  the `GPU` filter.

`DeviceType` models all five ggml members plus an `UNKNOWN` sentinel, and
`parse()` maps an unrecognised integer to `UNKNOWN` rather than raising: every
Mac lists an Accelerate `BLAS` device at raw type 3, so a three-member enum would
fail at first paint on a healthy machine, and ggml has added a member twice.

### Host memory comes from the OS

ggml's CPU device reports real available memory on native Windows and nowhere
else measured. Under WSL2 the figure is virtualised (26048.6 MiB total and free).
On an M2 with roughly 2 GB genuinely free it reported 8192.0 MiB total and
8192.0 MiB free, physical RAM restated twice. So `system_memory.available_bytes()`
asks the operating system: `MemAvailable` from `/proc/meminfo` on Linux, free
plus inactive pages from `vm_stat` on macOS, which is what a large allocation can
actually claim, and `sysconf` totals as the fallback rather than zero. The figure
matters because host memory is what separates `PARTIAL` from `TOO_BIG` on a
discrete card.

### Unified memory is one pool

Apple Silicon reports two views of one memory: Metal states
`recommendedMaxWorkingSetSize` (5461.3 MiB on the 8 GB M2) as both its total and
its free, while the host states the same memory again. Summed, an 8 GB Mac priced
as though it had 10.3 GB, with a refusal threshold of 10,581 MiB.

```python
UMA_HOST_FRACTION = 0.85

def unified_pool_bytes(working_set_bytes: int, host_bytes: int) -> int:
    return min(working_set_bytes, int(UMA_HOST_FRACTION * host_bytes))
```

Two limits apply and the smaller governs. The working set is a ceiling Metal will
not allocate past, and it is the figure llama.cpp's fitter subtracts its own
margin from, so discounting it again would refuse a model the runtime places.
Host memory is what is actually there, and it is the leg that lies: a snapshot,
while loading weights takes seconds during which another application can take
memory. The 0.85 is for that second job. Spending the working set as though it
were live sized a 28,672-token window on an 8 GB Mac with 2.3 GB reclaimable; the
load paged and took 43 seconds. A GPU that shares the CPU's description is the
signal that memory is unified: Apple Silicon reports the same part name for both.

### GPU status: four answers, not two

ggml answers an empty device list with exit 0 on two very different machines: a
laptop with no graphics card, and a workstation whose backend library did not
ship. Measured on Windows and Linux with a working card and `ggml-cuda.dll`
staged without its cudart, `--list-devices` prints `(none)` and exits 0, and
`GGML_BACKEND_DEBUG=1` changes nothing. Badging the second as the first would
mark every model as running on the processor, with no hint that the card is idle
because a file is missing. `gpu_status.classify()` reconciles ggml with the
operating system:

| ggml lists a `GPU` or `IGPU` | OS sees a GPU | Status |
|---|---|---|
| yes | either | `present` |
| no | yes | `broken_install` |
| no | no | `absent` |
| no | cannot say, and a CPU device was listed | `absent` |
| no | cannot say, and nothing was listed | `unknown` |

The OS half is `Win32_VideoController` through PowerShell on Windows,
`card*/device/vendor` under `/sys/class/drm` on Linux, and true on arm64 macOS.
Virtual adapters do not count: the Windows test machine carried a Parsec virtual
display beside its two real GPUs, and Linux skips the PCI vendor ids of QEMU,
virtio, VMware and VirtualBox displays. A probe that raises is treated as an
empty listing, so a card the OS can see still reads `broken_install`.

`present` means ggml listed a GPU, not that the budget is priced against one: an
integrated part counts here and is still skipped by `select_device()`. "Is the
runtime seeing the hardware" and "what will hold the layers" are different
questions, and conflating them would badge an AMD APU laptop as broken. The
status travels beside the budget on `GET /llm/system` and `GET /llm/catalog/local`,
never inside it, because a broken install must not read as a machine without a
card.

### Two budget modes

`build_budget()` answers two questions with the same subtraction.

- **Capacity** prices the catalog, a shelf of models someone might install later,
  which must not move with whatever the machine is doing right now. Host memory
  is the CPU device's total, which is physical RAM, minus 2 GiB, the reserve a
  host keeps for itself once a model is resident.
- **Live** decides a launch: this model, into this memory, now. Host memory is
  the operating system's reading as given.

Pricing the catalog against live free memory would make every large row read
`TOO_BIG` whenever a browser is open, a badge that lies in the direction users
notice. The 2 GiB reserve is only meaningful against physical RAM: when nothing
states the total, the live reading is a floor rather than another figure to
deduct from, because subtracting twice reported 0 GB on a busy 8 GB machine and
badged every model `Won't fit`.

Device memory is ggml's `free`, never a nameplate total. On the RTX 3050,
`nvidia-smi` reported 5699 of 6144 MiB free at idle and ggml 5158 MiB free after
context init: 986 MiB was gone before any weight loaded, about 445 to the desktop
and 541 to the backend context. `free` already excludes both, so an overhead term
on top would charge the same memory twice.

## The estimate

### Three numbers, not two

```text
need     = weights + mmproj + KV(window) + compute_buffers
resident = what the model must fit inside to run at full speed
refusal  = what physics allows at all
```

The two subtractions sit on opposite sides of the comparison, and collapsing
them into one `overhead` term made the first prediction wrong by 922 MiB.
Measured, Qwen3 4B at 16K on an RTX 3050 with 5,234 MiB free: treating the
1,028 MiB the fitter holds back as part of `need` predicts `FITS` with 378 MiB
spare, while llama.cpp spilled 602 MiB of weights and 320 MiB of KV.

`HardwareBudget` owns `resident` and `refusal`, because what they mean depends on
the machine. `usable_vram_bytes` is the device's free memory minus the fit
reserve.

| Machine | `resident_bytes` | `refusal_bytes` |
|---|---|---|
| Discrete GPU | `usable_vram_bytes` | `usable_vram_bytes` plus host memory |
| Unified memory | `usable_vram_bytes`, from the unified pool | host memory, never a sum |
| No GPU | host memory | host memory |

Assembling these in the estimator once badged every model on a CPU-only laptop as
spilling from a graphics card it does not have. With no GPU the two are the same
number, which makes `PARTIAL` unreachable there by construction rather than by a
special case. On unified memory the refusal threshold is host memory, because
Metal's working set bounds what Metal will allocate rather than what the machine
can hold. Measured: a 1.7B at 40,960 tokens projected 6,032 MiB against a
5,460 MiB working set, and llama.cpp ran it anyway, with part of the model on the
CPU backend, which reads the same chips without that ceiling. So `PARTIAL` stays
reachable on a Mac, between the pool minus the reserve and host memory, and
refusing that band would remove a real option from the users with the least
choice.

### The fit reserve is a flag, not a prediction

`fit_params_target` in llama.cpp's `common/common.h` defaults to 1 GiB per
device, platform independent. The Windows figure of 1,028.34 MiB was that
1024 MiB plus allocator rounding, and Metal names it under `-v`:

```text
common_params_fit_impl: projected to use 5752 MiB of device memory vs. 5460 MiB of free
common_params_fit_impl: cannot meet free memory target of 1024 MiB,
                        need to reduce device memory by 1315 MiB
```

`5752 - (5460 - 1024) = 1316`: the comparison is exact on a second backend. It is
also a CLI flag, `--fit-target`, in MiB per device, so the reserve is an input
the app controls rather than a number to predict, and
`usable = device_free - fit_reserve` holds by construction on every platform.
`LLAMA_CPP_FIT_MARGIN_BYTES` in `hardware/budget.py` is the one value: the budget
subtracts it, and `fit_target_mib()` hands it to the preset in MiB, plus any
projector's bytes.

### The four terms

`itemise()` returns `NeedItems`, the four terms separately (`weights_bytes`, which
is the file size, `mmproj_bytes`, `kv_bytes` and `compute_bytes`) rather than a
sum. A sum is untestable, because it can be right for compensating wrong reasons;
separate terms let a test assert that the weights do not move when the window
does; and the offload calculation needs to know which terms llama.cpp can move.
The projector is its own term because `--fit` does not count it, so a vision
model the sum calls resident can still fail to allocate, and because the fitter
cannot move it. A vision build installs with its projector, and its price
counts it ([`catalog.md`](catalog.md)).

### The KV cache

Architecture-derived and independent of how the weights were quantized, which is
what lets one header read price every build. Three modules, one question each.

**How wide one layer's entry is.** Ordinarily
`head_count_kv × (key_length + value_length) × bytes_per_element`, taken per
layer and summed, because llama.cpp sizes each layer from its own
`n_embd_k_gqa(il)`. A header that lists head counts per layer has each layer
charged its own count, and a sliding layer is charged `key_length_swa` and
`value_length_swa` where the header states them. Collapsing either to one number
and multiplying charged every layer as the widest: on a model whose layers
differ, 5,056 MiB against the 992 MiB the runtime allocates at 32,768 tokens
(commit 4bf49ff94, which does not name the model). For
a uniform model the sum is the product it replaced. For a latent
model (`kv_lora_rank > 0`, `mla_cache.py`) it is
`(kv_lora_rank + key_length_mla) × bytes_per_element`, because a DeepSeek-class
header reports a single KV head while the model has a hundred and more, and the
ordinary formula prices it enormously too large.

**Bytes per element** come from the block layout, not the bit width divided by
eight: `q8_0` stores 32 int8 weights plus one fp16 scale, so it costs 34/32 bytes
per element, not 1.0.

| | f32 | f16 / bf16 | q8_0 | q5_1 | q5_0 | q4_1 | q4_0 / iq4_nl |
|---|---|---|---|---|---|---|---|
| bytes per element | 4.0 | 2.0 | 34/32 | 24/32 | 22/32 | 20/32 | 18/32 |

The load plan only chooses between `f16` and `q8_0`; the others are priced, but
nothing chooses them.

**How many cells a layer allocates** (`kv_cells.py`). Not the token count. Every
cache is padded to 256 cells on every backend, and a sliding-window layer
allocates `min(pad(n_ctx), pad(n_swa + n_ubatch))`, because the batch being
processed sits in the cache beside the window it attends to. `n_ubatch` is
llama-server's default 512, and `n_seq_max` is 1, pinned by the `parallel = 1`
every preset writes.

**Which layers hold the whole window** (`sliding_window.py`). Three sources, in
the order llama.cpp consults them: a per-layer flag array in the header, then a
period in the header, then a table of 14 per-architecture defaults read from
llama.cpp at `b11050`. An architecture nobody has verified is absent from the
table rather than guessed, and absence prices every layer at full width, which
over-states memory in the only direction it is safe to be wrong in. Layers that
allocate a cache are `block_count - shared_kv_layers`: Gemma 3n and Gemma 4 reuse
an earlier layer's cache on their last blocks, and charging those layers would
over-state the window's cost on exactly the models chosen to be cheap on a small
machine.

The formula is exact on both backends measured. Qwen3 1.7B on Metal:
`2 × 28 layers × 8 KV heads × 128 × 2 bytes × 16384` = 1,792 MiB, reported as
`1792.00`, and 4,480 MiB at 40,960 cells. Qwen3 4B on Vulkan predicts 2,304 MiB
against `1984 + 320` measured.

### Compute buffers

Scratch is sized by the widest thing one layer computes, so it scales with the
model rather than being a fee every model pays alike. A constant fitted to a 1.7B
under-stated a 4B by about 70 MiB, more than the margin that decides a 12 GB
card's top row.

```python
activation_width = max(12 * n_embd,
                       4 * n_ff,
                       n_used * (2 * n_embd + 3 * n_ff_exp) + 3 * n_ff_shared)

flat  = int((activation_width * 512 + n_vocab * min(512, SLOTS)) * 4 * SAFETY)
total = flat + 5_120 * n_ctx
```

with `SAFETY = 1.20` and `SLOTS = 1`, matching the `parallel = 1` in every preset.

The safety factor and the per-token slope are fitted, not derived, and the module
says so. Qwen3 1.7B on Metal reported 102.24 MiB at 16,384 and 222.24 MiB at
40,960, so the slope is exact for that pair, 120 MiB over 24,576 tokens; a 4B on
Vulkan reported 143.62 MiB device plus 26.01 MiB host at 16,384. The backends
disagree about the flat half by more than the widths explain, so 1.20 covers both
rather than matching either, over-stating the 1.7B by about a third. At 1.10 the
4B came out at 0.97 of what Vulkan really allocated, and under-stating is the
direction that ships a confident badge about a model that spills. The module names
its upgrade path: replace the term with the machine's own residual after a first
load.

A header that states no widths falls back to the old constant line, 23 MiB plus
5,120 bytes per token: wrong in detail, but the measured floor for the smallest
model and better than pricing scratch at nothing. The manifest closes that path
for curated entries by requiring `embedding_length` and `feed_forward_length`
([`catalog.md`](catalog.md)).

### Offload counted in layers, not bytes

llama.cpp does not split a model by bytes. Its fitter fills devices with whole
layers, back to front, so the answer is a count of layers over the layer count:

```python
spilled   = items.total - resident_bytes
movable   = items.weights_bytes + items.kv_bytes
per_layer = movable / shape.block_count
fraction  = min(1.0, ceil(spilled / per_layer) / shape.block_count)
```

Only layers move: the projector is pinned by a flag, and the compute buffer
belongs to whichever device runs the graph. In the RTX 3050 run above, the 4B's
spill was 0.19 of the model; the byte ratio said 0.12 and the layer count gives
5/36, 0.14. All three agree on the verdict and the ordering, but the fraction
grades the reason line and gates the recommendation, so it is the fraction that
has to be right.

### Fit states

There is no `unknown`. Every row has a file size, so every row has a verdict.

| State | Condition | At load |
|---|---|---|
| `FITS` | `need <= resident` | every layer on the device, full speed |
| `PARTIAL` | `resident < need <= refusal` | `--fit` places some layers on the CPU; runs, slower |
| `TOO_BIG` | `need > refusal` at the floor | the only state that blocks an install |

`TOO_BIG` is judged at `CONTEXT_FLOOR_TOKENS`, not at the requested window: a
model that will not fit at the floor cannot be rescued by a smaller context, and
the remedy to offer is a smaller build. The property sweep found one more path:
when `need > refusal` at the requested window but the floor fits, the window is
refused rather than described as a partial offload. It is reachable on any
machine where the wider window needs more than the device and host can hold
together, a GPU machine with little free host memory included. The comment in
`estimate.py` says only a machine with no GPU reaches it, which is not so.

`FitVerdict.can_install` is `state is not TOO_BIG`, so `PARTIAL` installs exactly
like `FITS`. Eligibility, whether a model can chat here at all, is the catalog's
install gate and not a fit state ([`catalog.md`](catalog.md)). `offload_fraction`
stays on the verdict, and on the wire, because `PARTIAL` spans everything from
barely noticeable to unusable and the renderer must not recompute it.

`CONTEXT_FLOOR_TOKENS` is 8,192, not llama.cpp's own 4,096 reduction floor.
4,096 is too short once a system prompt, retrieved excerpts and a reply share the
window, so the fit search would settle there rather than spill weights it could
spill instead. What makes 8,192 safe is the chat context budget below.

### Speed tiers: one classification

A badge and a recommendation both start from the same verdict, and both used to
threshold `offload_fraction` on their own: the badge at a quarter and a half, the
recommendation at three quarters. A build could be starred while its own badge
said to expect it to be slow. `fit/speed.py` is now the only module that
thresholds the number:

```text
TOO_BIG          state is TOO_BIG
HEAVY_SPILL      f >= 0.5
MODERATE_SPILL   0.25 < f < 0.5
LIGHT_SPILL      f <= 0.25
FULL             state is FITS

RECOMMENDABLE_TIERS = {FULL, LIGHT_SPILL}
```

A recommended build can therefore never carry a warning, by construction:
the tiers it may be recommended at are exactly the tiers with no badge (below).
`catalog/local/test_catalog.py` holds it with a sweep of every curated build
against every budget shape.

### Badges

A badge is a **warning**, shown only when there is something to warn about. It
carries a `level` (`none`, `notice` or `refuse`), a verdict and one plain line
of why, all from `fit/copy.py`, which reads the speed tier and never the
runtime's name; the renderer shows the text verbatim and picks the style from the
level. On a discrete GPU:

```text
tier            level    verdict         reason
FULL            none     (none)          (none)
LIGHT_SPILL     none     (none)          Most of it runs on the graphics card.
MODERATE_SPILL  notice   Reduced speed   Too big for the graphics card, so part runs on the processor.
HEAVY_SPILL     notice   Reduced speed   Well over the graphics card's memory. Expect it to be slow.
TOO_BIG         refuse   Won't fit       Needs about 21 GB. This PC has 13.6 GB
```

On unified memory the card becomes "the GPU", the processor becomes "the CPU",
and "This PC" becomes "This Mac". With no GPU, `PARTIAL` is unreachable, so a
build either shows nothing or "Won't fit".

- **No badge where a build can be recommended.** `FULL` and `LIGHT_SPILL` carry
  none, so a recommended build never warns. A row that leads with another build,
  one in use or installed, can still show the star beside that build's warning.
  A light spill is still described, quietly, in the reason line.
- **A notice is amber, a refusal red.** The screen draws `notice` with the
  `warning` color token and `refuse` with `destructive`: reduced speed installs
  like any other build, and styling it as a failure would discourage a setup that
  works.
- **Decimal GB with one decimal, trailing zero dropped**, so a pair reads "21 GB"
  and "13.6 GB". Rounding the second to "14 GB" loses the half gigabyte that
  decided the answer.

No user-facing string here uses an em dash or a hyphen, only commas, full stops
and parentheses; `test_badge_copy.py` asserts it. A verdict priced from file size
alone, which is what a searched repo shows before its header is read, is marked
approximate, and the screen puts `~` before it.

## The load plan

`plan_load()` decides the window and the cache precision once, because llama.cpp
fixes context at load and it cannot be renegotiated mid-conversation. The ceiling
is the model's own `context_length` and the floor is
`min(CONTEXT_FLOOR_TOKENS, ceiling)`, so the cap beats the floor: a model trained
to 4,096 tokens is not asked for 8,192.

- **Prefer residency over window.** KV is allocated upfront and competes with the
  weights, so maximising context silently demotes a model out of GPU residency.
  The window widens only while the verdict stays `FITS`.
- **Prefer `f16` over `q8_0`.** Quality is identical, but a quantized cache needs
  a working flash-attention kernel, and without one llama.cpp falls back to CPU
  attention silently. `resident_precision()` returns `f16` if it keeps the
  build resident at the floor, else `q8_0`, else `None`, in which case the plan holds
  the floor at `f16`, since a cheaper cache buys nothing once layers spill. The
  choice is per model because on a 6 GB card `f16` KV at a 16K window cannot
  allocate while `q8_0` runs (see Measurements).
- **One precision rule for every caller.** `planned_precision()` is the same rule
  with the `f16` fallback, and the curated rows, the recommendation and a searched
  build's exact check all call it; a searched repo's listed builds are priced
  from their sizes and do not. Before it existed the badge priced `f16` while the
  loader chose `q8_0`, so a row read "Reduced speed" for a model the runtime then
  placed entirely on the device.
- **A fixed set of candidates rather than a continuous search**, so every window
  a person can see is one a test can enumerate: the rungs
  `CONTEXT_RUNGS = (8192, 16384, 32768)` that lie between floor and ceiling, the
  model's own trained length, so a model is not held below what it was trained
  for, and the floor, so the search never returns nothing.
- **Two budgets, and widening stays inside the tighter one.** Capacity decides
  the verdict, so the plan agrees with the badge the catalog showed. Live caps
  widening only, because context past the floor is opportunistic and on unified
  memory comes out of the pool the OS is using. A cap must not raise a ceiling, so
  widening uses whichever budget has less resident headroom: widening against a
  more generous live budget and reporting against capacity once produced a plan
  that said `PARTIAL` for a row badged `FITS`.

On the shipped manifest, a 16 GB M4 keeps Qwen3 14B resident only with a `q8_0`
cache at the 8,192 floor, while the smaller models there load at `f16` with a
wider window.

## The chat context budget

Because the floor is 8,192 rather than one fixed wide window,
`modules/chat/budget.py` prices the four named parts of a turn against the
model's real window:

| Part | Tokens | Basis |
|---|---|---|
| Answer reserve | 1024 | Reserved first. llama.cpp stops a reply wherever the window runs out, so spending this on history is how a good answer gets cut off mid-sentence with no error at all. |
| System prompt | 400 | A rendered prompt plus the grounding header at the largest tier. Approximate. |
| Excerpts | 2400 | Retrieval already caps chunks at 480 tokens and 5 hits, so this holds before retrieval runs. |
| Question | 1024 | The user's message, so one turn cannot claim the whole window. A share, not a limit (see Known gaps). |

History gets what is left, `max(0, n_ctx - 4848)`: 3,344 tokens at the 8,192
floor, growing with the window, so a narrower window means a shorter history
rather than a turn that silently exceeds the window. The answer request's
`max_tokens` is the 1,024 reserve.

An unknown window is not a narrow one. A remote endpoint reports no `n_ctx`, so
history falls back to the previous constant, 3,000 tokens, and
`answer_max_tokens()` returns `None`: capping a reply to this app's reserve on an
endpoint whose real window might be far larger would truncate answers for a limit
that was never theirs.

History is priced by the model's own tokenizer where it can be: `token_count()`
calls llama.cpp's `/tokenize`, proxied to the loaded worker the same way `/props`
is, because the fallback heuristic, about four characters per token, under-counts
dense text by 15 to 20%. `None` means no clean count (no such endpoint, a
transient failure, or a remote model), and the turn falls back to the estimate
rather than reading `None` as zero; `build_messages()` never mixes the two within
one turn.

## Measurements

Taken against llama.cpp `b11050` (some earlier figures at `b11043`) on an M2 8 GB
and on an RTX 3050 with a Ryzen 5 9600X.

### Fit terms

Qwen3 4B Q4_K_M at `-c 16384`, `--fit` on, RTX 3050 with 5,234 MiB free, from
llama.cpp's own allocation log:

| Buffer | MiB |
|---|---|
| `Vulkan0` model | 2078.04 |
| `CPU_Mapped` model, spilled | 602.16 |
| `Vulkan0` KV | 1984.00 |
| `CPU` KV, spilled | 320.00 |
| `Vulkan0` compute | 143.62 |
| `Vulkan_Host` compute | 26.01 |
| `Vulkan_Host` output | 2.32 |
| Placed on device | 4205.66 |
| Fit reserve, left unused | 1028.34 |

Qwen3 1.7B at `-c 16384` on the M2 placed `1050 + 1792 + 102` MiB of model, KV
and compute on `MTL0` against the fitter's own projection of 2944, so the
three-term need is exact on Metal too. 243.43 MiB of the model stayed on the CPU
at "offloaded 29/29 layers to GPU", because the non-repeating tensors are
host-side even at full offload, and Metal reports `0.00 MiB` buffers during the
fitter's probe pass, so anything scraping buffer sizes must ignore that pass.

### The estimator against those measurements

| | KV predicted | KV measured | Compute predicted | Compute measured |
|---|---|---|---|---|
| 4B at 16384, Vulkan | 2304 MiB | 2304 MiB | 172 MiB | 170 MiB |
| 1.7B at 16384, Metal | 1792 MiB | 1792 MiB | 138 MiB | 126 MiB |
| 1.7B at 40960, Metal | 4480 MiB | 4480 MiB | 258 MiB | 246 MiB |

KV is exact. Compute is over in every case, which is the safe direction and the
reason the safety factor is 1.20.

### Offload and speed

Qwen3 4B Q4_K_M, `-ngl` setting the fraction directly so model size is held
constant, f16 KV, `-p 512 -n 300`, Vulkan, RTX 3050:

| ngl | `f` | pp512 (t/s) | tg300 (t/s) |
|---|---|---|---|
| 99 | 0.00 | 1805.50 ± 1.75 | 52.45 ± 0.17 |
| 28 | 0.22 | 1454.68 ± 0.93 | 33.17 ± 0.25 |
| 18 | 0.50 | 1206.29 ± 9.86 | 19.85 ± 1.06 |
| 9 | 0.75 | 1027.97 ± 26.10 | 12.93 ± 0.43 |
| 0 | 1.00 | 907.43 ± 26.49 | 13.13 ± 0.67 |

Fully on the CPU, prefill still runs at half device speed while decode drops to a
quarter, and this app is prefill-dominated, roughly 8,000 prompt tokens against
300 decoded. The slowdown fits `1 / (f × r + 1 − f)` with `r = BW_gpu / BW_cpu`
near 4 (131 GB/s effective on the device against 33 GB/s on the host). `r` is
roughly 12 on a 4090 and approaches 1 on unified memory, so a threshold
calibrated on a 3050 is not automatically conservative elsewhere.

### KV precision

`f16` KV at a 16K window on a 6 GB card:

```text
ggml_vulkan: Device memory allocation of size 316407808 failed.
ggml_vulkan: vk::Device::allocateMemory: ErrorOutOfDeviceMemory
llama_bench: error: failed to create context
```

`q8_0` at the same depth runs. Do not quote the depth-0 decode rates (52.47 `f16`
against 51.34 `q8_0` t/s) as `q8_0`'s cost: an almost empty cache's precision
cannot matter, and `f16` at 16K depth cannot allocate on this card. `q8_0` at
depth 16,384 decodes at 27.46 t/s, and that halving is the cost of attending over
a long context, not of quantizing it. The GPU backend comparison behind shipping
Vulkan alone is in [`../../proposals/cuda-backend.md`](../../proposals/cuda-backend.md).

## How it is tested

Unit tests under
[`surfsense_local/backend/tests/unit/llm/`](../../../surfsense_local/backend/tests/unit/llm/)
in `fit/`, `gguf/` and `hardware/`, with `fit/test_properties.py` sweeping shapes,
windows, precisions and budget shapes; `catalog/local/test_catalog.py`
holds the badge to the load, and `tests/unit/chat/test_budget.py` the chat budget.

## Known gaps

- Live host memory reads 0 on Windows: `system_memory.available_bytes()` has no Windows branch and `os.sysconf` does not exist there, and `Device.reports_live_memory`, which tells a live reading from a restated total, is never read. On a Windows machine with no GPU every model is therefore planned at the 8,192 floor; capacity mode is unaffected because it reads the CPU device's total.
- The question's 1,024-token share is not enforced: `MessageText` in `modules/chat/schemas.py` sets no maximum length, so a longer question can push a turn with a full history past the window.
- The `q8_0` preference is unmeasured: nobody has timed a resident `q8_0` cache against a small `f16` spill on prompt rate, and published figures report quantized caches generating materially slower.
- The light-spill boundary may be tight: `LIGHT_SPILL` ends at 0.25, which puts Qwen3 8B on a 6 GB RTX 3050 (0.33 by layers) out of the recommendation although its owner runs it without noticeable lag; one prefill and decode measurement of that configuration against the resident 4B settles it, and moving the boundary moves the badge and the star together.
- The weights term is unconfirmed against the pinned files: the measured model buffers exceeded them (2,680 MiB against 2,382 for the 4B, 1,294 against 1,056 for the 1.7B), probably because those runs used another publisher's build, and if not, the largest term is under-estimated by 12 to 22%.
