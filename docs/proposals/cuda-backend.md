---
status: deferred
code:
  - surfsense_local/electron/scripts/fetch-llamacpp.mjs
  - surfsense_local/electron/electron-builder.yml
---

# CUDA as an optional second backend

> Owns: the Windows GPU backend payload and multi-device selection. Extends
> the llama.cpp runtime ([`local-models/runtime.md`](../architecture/local-models/runtime.md)),
> which ships **Vulkan on every platform off Apple Silicon** ([ADR 0012](../adr/0012-vulkan-only-gpu-backend.md)).
> Nothing here is required by that runtime, and nothing here changes application code.
> *Phase 7* below means that llama.cpp runtime work; the numbered steps 8.0 onwards
> are this proposal's own.
>
> This proposal exists so the decision is written down with its evidence, not
> so it gets built. It ships only if the measurement in **8.0** comes back
> materially different from the one in the Appendix.

## Goal

Add CUDA alongside Vulkan on Windows, as a packaging change, when and only when
a measurement says it is worth 685 MB.

## Why this is a separate phase

Phase 7 ships Vulkan everywhere except the Mac:

```text
Mac       Metal      11 MB      no alternative exists
Windows   Vulkan     86 MB      on disk
Linux     Vulkan     85 MB      on disk
```

That is not a compromise position. It is what the app **already does today**:
`pruneCudaRunners()` in `electron/scripts/fetch-ollama.mjs` deletes the CUDA
runners out of the bundled Ollama at build time, because `cuda_v12 + cuda_v13`
was 1.7 GB of a 1.8 GB payload and blew the 2 GB `makensis` ceiling. Every
SurfSense user with an NVIDIA card is on Vulkan right now, and the `ponytail`
beside that function records the intended fix — an opt-in post-install pack,
which the airgapped rule later ruled out.

So CUDA is not a regression to defend against. It is a **new capability**, newly
affordable because dropping Ollama frees ~500 MB. This document decides whether
to buy it.

**Measured, it is worth 0.66 seconds per turn.** The full numbers are in the
Appendix. The one-line version: CUDA leads Vulkan by **9.1% on `pp512`, 10.2% on
`pp8192`, and 2.1% on decode** — not the 36–40% that earlier drafts of phase 7
claimed, which is why that claim was removed rather than carried forward.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| **Ship it?** | **No, not yet.** Vulkan only | 685 MB for a measured 0.66 s on an 11 s turn. The gap is real and small. Revisit on new evidence, not on a schedule. |
| **Platform** | **Windows only**, if ever | Linux is the weakest case: AppImage is a single downloadable file, Linux ships CUDA **13.3** against Windows' **13.4** so covering both pins two majors, and Linux desktop plus recent NVIDIA is the smallest population. Hermes reaches the same conclusion — its asset table has no `cuda` key for Ubuntu at all. |
| **Mac** | **Never** | Apple Silicon has no NVIDIA hardware. Metal is built into macOS. Not a decision. |
| **Coexistence** | Both backends, one flat folder | Verified: ggml loads every `ggml-*.dll` it finds and registers all of them. CUDA is probed first, so it wins automatically when present. |
| **Code changes** | **None** | The backend is a file in a folder, not a branch. `ggml_backend_load_best()` does the selection. Adding CUDA is `fetch-llamacpp.mjs` plus a rebuild. |
| **Device selection** | First device with `type == GPU`. **Never sum** | Specified in [`local-models/fit.md`](../architecture/local-models/fit.md), and needed there anyway. What this phase adds is the duplicate case: with both backends loaded the same physical card appears twice, both typed `GPU`. |
| **CUDA version** | 13.4, Windows x64 | Requires Turing (7.5)+. Shipping 12.4 as well for Pascal costs another ~645 MB — that is what made Ollama's archive 1.8 GB. Pre-Turing cards fall through to Vulkan automatically. |
| **Reversibility** | Cheap in both directions | Adding CUDA is four files. Removing it is deleting four files. Neither touches a contract, a schema or a migration. |
| **Diagnostics** | Mandatory if shipped | A missing cudart is **silent**: the app reports no GPU, exit 0. See **Failure behavior**. |
| **Quantized KV** | A real argument **for** CUDA, and the only one that strengthened | `q8_0` KV requires flash attention. CUDA's FA path is the mature one; Vulkan has two, and the vendor-neutral `GL_KHR_cooperative_matrix` path used by AMD and Intel was only optimised in mid-2026 and carries an open report of extreme degradation on AMD. Since the fit estimate ([`local-models/fit.md`](../architecture/local-models/fit.md)) now selects `q8_0` whenever it converts a spill into residency, the backend's FA quality stops being cosmetic. Note CUDA's `GGML_CUDA_FA_ALL_QUANTS` build flag decides which K/V combinations get fused kernels. |

## Boundaries

```text
  packaging ──── fetch-llamacpp.mjs stages backend libraries
        │              Vulkan always · CUDA optionally, Windows only
        ▼
  ggml_backend_load_all() ── loads every ggml-*.dll in the executable's dir
        │                    probes cuda before vulkan · silent skip on failure
        ▼
  device list ── may contain the SAME card once per loaded backend
        │
        ▼
  select_device() ── first type == GPU wins. This IS backend selection.
        │
        ▼
  HardwareBudget ── one device, never a sum
```

Everything above `select_device()` is packaging. Everything below is phase 7 and
does not change. That is the whole point of keeping this separate.

## Contracts

> **Provenance.** Every number and every listing in this document was measured on
> a Windows 11 (26200) machine with an RTX 3050, against llama.cpp `b11050`. The
> ggml calls were made live through `ctypes`. Nothing here is reasoned from
> documentation.

### The device listing this phase exists to handle

With both backends staged in one folder, this is what a real NVIDIA Windows
machine reports:

```text
device count  4
  [0] CUDA0    type=GPU    6143.5 MiB total, 5166.0 MiB free   NVIDIA GeForce RTX 3050
  [1] Vulkan0  type=GPU    6002.0 MiB total, 5166.0 MiB free   NVIDIA GeForce RTX 3050
  [2] Vulkan1  type=ACCEL 16198.3 MiB total                    AMD Radeon(TM) Graphics
  [3] CPU      type=CPU   31884.6 MiB total                    AMD Ryzen 5 9600X
```

Four entries, **three** pieces of hardware. Read it carefully, because three
separate traps are visible in it:

1. **`CUDA0` and `Vulkan0` are the same physical card.** Note the identical
   `5166.0 MiB free`. Summing device memory reports 12 GB of GPU on a 6 GB card,
   and every fit badge is then wrong in the dangerous direction — telling users a
   model fits when it cannot.
2. **Both are typed `GPU`.** Filtering on device type does **not** deduplicate
   them. Type separates the discrete card from the integrated one; it does not
   separate backends.
3. **The integrated GPU advertises more memory than the real one** — 16198 MiB
   against 6002 MiB, because it is carving from system RAM. Picking the device
   with the most memory picks the slowest one. This trap exists under Vulkan
   alone and is not specific to this phase.

`total` also differs between backends for the same card (6143.5 vs 6002.0 MiB):
CUDA reports the device total, Vulkan the heap size. A 141 MiB disagreement,
small enough not to matter and large enough to confuse someone reading logs.

### The selection rule

**`select_device()` is specified in [`local-models/fit.md`](../architecture/local-models/fit.md),
under Device selection**, and is required there regardless of whether this phase ever ships: the
integrated-GPU trap exists under Vulkan alone. It takes the first device with
`type == GPU`, never aggregates, and treats `ACCEL` as not a GPU.

What this phase adds is the **duplicate** case. Under Vulkan alone a machine
lists each physical device once. With both backends loaded the same card is
listed once per backend, **both typed `GPU`** — so type filtering, which is
sufficient to separate discrete from integrated, is not sufficient to separate
backends. "First wins" already handles it, because ggml orders CUDA ahead of
Vulkan; the requirement is simply that nothing downstream aggregates.

### Packaging shape

Four files land beside `llama-server.exe`, in the same flat folder as everything
else. No subdirectory, no search path, no environment variable.

| File | Size |
|---|---|
| `ggml-cuda.dll` | 138 MB |
| `cublasLt64_13.dll` | **492 MB** |
| `cublas64_13.dll` | 55 MB |
| `cudart64_13.dll` | 0.55 MB |

From two pinned assets, both checksummed:

```text
llama-b<build>-bin-win-cuda-13.4-x64.zip     150.1 MB
cudart-llama-bin-win-cuda-13.4-x64.zip       423.5 MB
```

**The archives overlap almost entirely**, so the marginal costs are wildly
asymmetric and worth knowing before anyone estimates from the sum:

| Starting from | Adding | Costs |
|---|---|---|
| Vulkan build | CUDA | **+685 MB** |
| CUDA build | Vulkan | **+42 MB** |

Both archives are the same CPU base plus one backend library. All the weight is
`cudart`, and 72% of `cudart` is the single file `cublasLt64_13.dll`.

On-disk totals, measured:

```text
Vulkan only         86 MB
CUDA only          706 MB
both               748 MB      (not 792 — the CPU base is shared)
```

### Out of scope

Linux CUDA, ROCm, SYCL and OpenVINO. The assets exist
(`llama-b<build>-bin-ubuntu-cuda-13.3-x64.tar.gz`, 149.1 MB, plus a 410.2 MB
cudart) and Hermes' comment that Linux CUDA is unavailable is **stale** — but
none of them is proposed here. Anyone adding one should read **8.2** first,
because the device-duplication rule generalises to every additional backend.

Phase 7's runtime contract, catalog, fit states, manifest and recommendation
policy are untouched.

## Phases

### 8.0 — Re-measure, and only then decide

**This phase gates every other phase.** Nothing below happens until this
produces a number materially better than the Appendix's.

```bash
llama-bench -m <small gguf> -p 512,8192 -n 300 -ngl 99
```

Run against both staged builds on the same card, same model, same build number.

- `-p 8192` because that is the real prefill load. The default 512 understates a
  RAG workload, and the gap varies with sequence length.
- `-ngl 99` so both runs are fully GPU-resident and the comparison is compute,
  not offloading.
- Confirm from the log that Vulkan chose device 0. If decode collapses, it picked
  the integrated GPU and the run is void.

**What the follow-up measurements changed.** Since this document was written,
the offload sweep in [`local-models/fit.md`](../architecture/local-models/fit.md) established two things that
bear on the decision:

- **The roofline holds with `r ≈ 4` on a 6 GB card**, so the speed cost of
  spilling is now predictable rather than guessed. CUDA's advantage over Vulkan
  on the same card was 2.1% on decode, which moves `r` to ~4.1 — immaterial.
- **Prefill degrades half as much as decode under offload** (0.50 against 0.25
  fully on the CPU). Because this app is prefill-dominated, the workload is
  *less* sensitive to backend decode speed than a chat or agent app would be —
  which weakens the case for CUDA further, since its measured lead was almost
  entirely in prefill (10.2%) and nearly absent in decode (2.1%).

Together these make the 0.66 s per turn figure below more, not less, reliable.

**Decision rule, fixed in advance so the result cannot be rationalised:**

| Result | Action |
|---|---|
| CUDA leads by **< 15%** on `pp8192` | Vulkan stands. Close this phase. |
| **15–30%** | Judgement call. Weigh against 685 MB and the installer size. |
| **> 30%** | Ship it. Proceed to 8.1. |

The Appendix measurement came back at **10.2%**. Re-measuring is worthwhile only
on a materially different NVIDIA generation — Ada or Blackwell, or a Turing card
at the CUDA 13 floor. Re-running on another Ampere card is not new evidence.

**Tests:** none. This is a measurement, and its output is a decision.

### 8.1 — Package

`fetch-llamacpp.mjs` gains a second Windows asset, pinned by build number **and
SHA-256** like the first.

- Stage both archives into the same flat `resources/llamacpp/`.
- Prune as phase 7 already does: `llama-server` plus libraries, nothing else.
- Retain upstream licence and notice files for the CUDA archives.
- Code signing, notarization and antivirus smoke tests now cover four more
  binaries, one of which is 492 MB. Expect signing time to rise.
- Recheck the `makensis` ceiling. Phase 7 leaves ~470 MB of headroom against
  today's installer; this consumes ~605 MB compressed of it.

**Tests:** staged-checksum verification for both archives; the packaged folder
contains all four files; `llama-server --list-devices` from the final packaged
path reports a `CUDA` device on an NVIDIA runner.

### 8.2 — Harden device selection

`select_device()` ships in phase 7. **No new code here** — this step is
only the extra test coverage the duplicate case needs, since phase 7 cannot
produce a listing containing the same card twice.

**Tests:**

- The four-device listing above, verbatim as a fixture, selects `CUDA0`.
- The same listing with `ggml-cuda.dll` absent selects `Vulkan0`.
- A Vulkan-only listing with a 6 GB discrete card and a 16 GB integrated one
  selects the **discrete** card — the regression that would otherwise place
  layers on the slow chip.
- `usable_vram_bytes` never exceeds any single device's memory. Asserted against
  the duplicate listing, where a naive sum yields 12 GB on a 6 GB card.
- A CPU-only listing returns `None` and `has_gpu` is false.

### 8.3 — Diagnose a broken install

**Mandatory if this phase ships.** Without it, one packaging slip produces an app
that silently never uses the GPU.

A missing cudart does not fail loudly. Measured on both Windows and Linux with
the card present and `ggml-cuda.dll` staged:

```text
$ llama-server --list-devices
Available devices:
  (none)
$ echo $?
0
```

No dialog, no warning, no non-zero exit. `GGML_BACKEND_DEBUG=1` changes nothing.
`ldd` shows why — `libcudart.so.13 => not found` — but the program never says so.

So cross-check against the operating system:

| OS reports a GPU | ggml reports a GPU | Meaning |
|---|---|---|
| yes | yes | normal |
| no | no | genuine CPU-only machine, badge accordingly |
| **yes** | **no** | **broken install.** Say so. Never badge CPU-only. |

Sources: `Win32_VideoController` on Windows, `/sys/class/drm` on Linux. Filter
virtual adapters — the measured machine carried a `Parsec Virtual Display
Adapter` alongside its two real GPUs.

Odysseus codes around this same failure explicitly, warning *"nvcc found but CUDA
runtime (libcudart.so) is not visible — building llama-server for CPU only"*.
Independent confirmation that it is common enough to handle rather than assume
away.

**Tests:** all three rows above as fixtures; the mismatch row produces a distinct
error state, not a `has_gpu: false` budget.

### 8.4 — Verify on real hardware

CI runners have no GPU, so `--list-devices` on a runner proves only that the
binary starts. A real NVIDIA machine must confirm, once per pinned build:

- `--list-devices` reports a `CUDA` device from the packaged resource path.
- The probe reports a `CUDA0` device from inside the **frozen backend process**,
  not from a shell in the llama.cpp folder. See **Failure behavior** — this is
  the failure most likely to survive to release.
- A model loads and answers with all layers on the GPU.
- `taskkill /PID <router> /T /F` reaps the model workers, not just the router.

## Failure behavior

- **cudart missing** — silent `(none)`, exit 0. Covered by 8.3. This is the
  failure mode that ships if 8.3 is skipped.
- **Probe run from the wrong directory** — `ggml_backend_load_all()` searches
  **the host executable's own directory**. From the frozen `surfsense-api.exe`
  in `resources/backend/`, it finds nothing in `resources/llamacpp/` and reports
  zero devices on a machine with a working card. Loading the libraries by
  absolute path is **not sufficient**; the backend scan is separate. Verified:
  `device count 0` from `python.exe`, `device count 2` after `chdir` to the
  library folder, same machine, same second.
- **`GGML_BACKEND_PATH` is not the fix.** It expects a **file**, not a
  directory. Passing a directory logs `load_backend: failed to load <dir>` and
  leaves the count at zero.
- **Pre-Turing NVIDIA card** — the CUDA backend is skipped silently and Vulkan
  runs. Correct behavior, no message needed.
- **Flash attention not engaged** — with CUDA present this is less likely than on
  Vulkan, but the failure shape is identical: quantized KV falls back to CPU
  attention with no warning and near-zero device utilisation. This is the
  failure [`local-models/runtime.md`](../architecture/local-models/runtime.md) describes under **Failure behavior**,
  and nothing detects it at runtime today; shipping CUDA makes it less likely,
  not detectable.
- **Duplicate devices** — not a failure, the normal state. Handled by
  `select_device()`.
- **Vulkan loader missing on Windows** — not observed. `vulkan-1.dll` is present
  in `C:\WINDOWS\System32` on a stock install.

## Tests

Collected from the phases above; all are unit tests over fixtures except the
last two.

- `select_device()` across five listings: both backends, CUDA absent,
  Vulkan-only with discrete plus integrated, CPU-only, and the duplicate case
  asserting no aggregation.
- Broken-install detection across the three OS-versus-ggml rows.
- Two-handle `ctypes` loading on Windows (`ggml.dll` **and** `ggml-base.dll`);
  single-handle on Linux (`libggml.so`). A regression here is an
  `AttributeError` at startup, not a wrong answer.
- Probe succeeds when the working directory is the library folder and reports
  zero when it is not — the second assertion is what stops the search-path bug
  from returning.
- Packaging: checksums for both archives; all four files present in the packaged
  folder.
- **Manual, on real NVIDIA hardware, once per pinned build:** 8.4's four checks.

## Acceptance

Only meaningful if 8.0 clears the bar. In order:

- A measurement exists, at `pp8192`, on a named GPU, recorded in the Appendix
  with its build number.
- A Windows machine with an RTX card runs on CUDA from the installer alone, no
  post-install download.
- A pre-Turing NVIDIA machine runs on Vulkan with no error shown.
- A machine with no usable GPU runs on CPU with no error shown.
- A machine with a card but a broken CUDA payload says **broken install**, and
  does not badge itself CPU-only.
- Fit badges on a dual-GPU machine price against the discrete card's memory
  alone, never a sum.
- The installer stays under the `makensis` ceiling.

## Appendix — measurements

All taken 19 Sep 2026 on one machine, against llama.cpp `b11050` (`60b06ab9a`).

**Hardware**

```text
Windows 11 26200  ·  WSL2 Fedora 44 (glibc 2.43) on the same box
AMD Ryzen 5 9600X, 6C/12T, 31884.6 MiB RAM
NVIDIA GeForce RTX 3050, 6144 MiB, driver 616.92, compute capability 8.6
AMD Radeon(TM) Graphics (integrated)  ·  Parsec Virtual Display Adapter
```

Compute capability **8.6** clears CUDA 13's Turing 7.5 floor, so this card
validates the version decision rather than testing its edge.

**The benchmark.** Qwen3 4B Q4_K_M (2.32 GiB, 4.02 B params), `-ngl 99`, fully
GPU-resident on both runs.

| test | CUDA 13.4 | Vulkan | CUDA advantage |
|---|---|---|---|
| `pp512` | 1929.18 ± 8.84 | 1767.62 ± 1.43 | **+9.1%** |
| `pp8192` | 1537.12 ± 5.84 | 1394.77 ± 5.04 | **+10.2%** |
| `tg300` | 52.19 ± 0.22 | 51.13 ± 0.11 | **+2.1%** |

Error bars are 0.1–0.9%, so the gap is real and the size of the gap is not in
doubt on this card.

**What it is worth**, at phase 7's real turn shape — ~8,000 prefill tokens
(`HISTORY_BUDGET_TOKENS = 3000` plus ~8K of grounding) against ~300 decoded:

```text
              prefill    decode     total turn
CUDA           5.33 s     5.75 s      11.1 s
Vulkan         5.87 s     5.87 s      11.7 s
                                    ─────────
difference                            0.66 s      (5.7%)
```

**685 MB for 0.66 seconds.** That is the trade, stated plainly.

**The 36–40% claim is retired.** Earlier drafts of phase 7 cited *"CUDA leads
Vulkan ~36–40% on `pp512` and ~10% on `tg128`."* Measured here: **9.1%** and
**2.1%** — off by roughly 4× and 5×. No public head-to-head benchmark on
identical NVIDIA hardware was found to corroborate either figure, so this
measurement is the only direct evidence either way.

A likely cause is that the older figure predates Vulkan reaching the tensor
cores. This card reports `matrix cores: NV_coopmat2v` under Vulkan, against
`matrix cores: none` for the integrated AMD chip. **Treat that as a hypothesis,
not a finding:** llama.cpp discussion #12548 notes the `matrix cores:` line is
not a reliable indicator of the fast path, since current builds report
`KHR_coopmat` on hardware that previously reported `NV_coopmat2` at identical
throughput. The throughput above was measured directly and does not depend on
that explanation.

**Timings**

| Call | Value |
|---|---|
| `ggml_backend_load_all()`, CUDA only | 77 ms |
| `ggml_backend_load_all()`, Vulkan only | 136 ms |
| `ggml_backend_load_all()`, both | 205 ms |
| `ggml_backend_dev_memory()` first call, CUDA | 47.89 ms |
| `ggml_backend_dev_memory()` first call, Vulkan | 3.50 ms |
| `ggml_backend_dev_memory()`, CPU | 0.01 ms |

No Metal-style cold-compile penalty off Apple Silicon; phase 7's advice to warm
the probe in the background is a Mac concern.

**VRAM accounting**, same card, three sources:

| Source | Total | Free |
|---|---|---|
| `nvidia-smi`, idle | 6144 MiB | 5699 MiB |
| ggml, after CUDA context init | 6143.5 MiB | 5158–5166 MiB |
| ggml, Vulkan | 6002.0 MiB | 5166.0 MiB |

**986 MiB of 6144 is gone before a single weight loads** — ~445 MiB to the
desktop, ~541 MiB to the CUDA context. Phase 7's 1,024 MiB overhead placeholder
is within 4% of that, but note the double-counting trap: ggml's `free` has
**already** subtracted both. Budget from `free` and add ~1 GB again and the same
memory is charged twice, demoting rows that fit.

**Symbols are split across two libraries**, and the intuitive choice fails:

| Library | Exports |
|---|---|
| `ggml.dll` / `libggml.so` | `ggml_backend_load_all`, `dev_count`, `dev_get` |
| `ggml-base.dll` / `libggml-base.so` | `dev_name`, `dev_description`, `dev_type`, `dev_memory` |

Linux resolves through the ELF dependency, so one `CDLL(libggml.so)` handle
works. **Windows needs both handles** — PE exports do not chain, and loading
`ggml.dll` alone raises `AttributeError: function 'ggml_backend_dev_name' not
found`.

**Assets and sizes at `b11050`**, verified against the live release. Phase 7's
figures were all confirmed to the megabyte.

| Asset | Size |
|---|---|
| `llama-b11050-bin-macos-arm64.tar.gz` | 11.2 MB |
| `llama-b11050-bin-win-vulkan-x64.zip` | 31.8 MB |
| `llama-b11050-bin-win-cuda-13.4-x64.zip` | 150.1 MB |
| `cudart-llama-bin-win-cuda-13.4-x64.zip` | 423.5 MB |
| `llama-b11050-bin-ubuntu-vulkan-x64.tar.gz` | 30.4 MB |
| `llama-b11050-bin-ubuntu-cuda-13.3-x64.tar.gz` | 149.1 MB |
| `cudart-llama-b11050-bin-ubuntu-cuda-13.3-x64.tar.gz` | 410.2 MB |

**Linux ships CUDA 13.3, Windows 13.4.** Covering both means pinning two CUDA
majors with separate cadences.

**What other projects do**, and why none of it decides this:

| Project | Backend policy | Bundles? |
|---|---|---|
| Hermes (`hermes_cli/local_runtime/`) | CUDA → Vulkan → CPU; **no Linux CUDA** | No — downloads per machine |
| Odysseus | CUDA → ROCm → Vulkan → CPU | No — **compiles** on the user's machine |
| Ollama | ships both CUDA majors | **Yes** — 1.8 GB archive |
| SurfSense today | Vulkan | Yes, with CUDA pruned at build time |

Hermes and Odysseus both prefer CUDA, and **neither pays for it** — an NVIDIA
user fetches or builds CUDA, everyone else gets Vulkan, nobody carries unused
weight. Their preference is evidence the gap is real; it is not evidence it is
worth 685 MB bundled, because they never face that question.

Ollama is the only true bundling precedent, and its answer produced the 1.8 GB
archive that `pruneCudaRunners()` exists to cut down.

## References

- [`ggml-backend-reg.cpp`](https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-backend-reg.cpp) — `ggml_backend_load_best()`, executable-directory search, silent skip on `dlopen` failure
- [llama.cpp discussion #12548](https://github.com/ggml-org/llama.cpp/discussions/12548) — coopmat2 on Vulkan, and why the `matrix cores:` line is not a reliable indicator
- [llama.cpp discussion #10879](https://github.com/ggml-org/llama.cpp/discussions/10879) — Vulkan backend performance
- [CUDA / ROCm / Vulkan scoreboard](https://knightli.com/en/2026/04/23/llama-cpp-gpu-benchmark-cuda-rocm-vulkan-scoreboard/) — CUDA-only; notes the absence of same-hardware backend comparisons
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) `hermes_cli/local_runtime/binaries.py` — `select_backend()`, the asset table, the `cuda → vulkan → cpu` ladder
- [odysseus-dev/odysseus](https://github.com/odysseus-dev/odysseus) `routes/cookbook_helpers.py` — the `_odysseus_has_cudart()` check and its warning
- `electron/scripts/fetch-ollama.mjs` — `pruneCudaRunners()`, the 2 GB `makensis` ceiling, and the ponytail this phase answers
