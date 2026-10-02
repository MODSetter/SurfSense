# Resource usage

Settings › Resources shows the machine's CPU, RAM, graphics memory and GPU load, with the app's share of each in the brand color. When the machine is full, a user can tell whether SurfSense is the cause or something else is, and see which runtime holds what. It reads the process table and the operating system's own counters. Nothing leaves the machine.

**Code:** [`surfsense_local/backend/modules/resource_usage/`](../../surfsense_local/backend/modules/resource_usage/), [`surfsense_local/frontend/src/features/resources/`](../../surfsense_local/frontend/src/features/resources/), [`surfsense_local/electron/src/main/sidecars/python.ts`](../../surfsense_local/electron/src/main/sidecars/python.ts)
**Decisions:** [ADR 0016](../adr/0016-no-telemetry.md)

```text
  panel ────── GET /system/usage every 2 s, only while Settings › Resources is open
     ▼
  sampler ──── parent_map()          one snapshot of the process table
     │         branches(shell pid)   every process under Electron's main process
     │         engine_of(name)       each child of the shell names its branch
     │         psutil per process    CPU percent (a rate) and resident size
     │         GPU reader            per platform, below
     ▼
  assemble() ─ machine figure, the app's share, one row per engine
```

## What counts as the app

Electron passes its main process's pid to the API as `SURFSENSE_LOCAL_SHELL_PID`. Everything under it is the app: the sidecars, llama-server's per-model workers, and Chromium's renderer and GPU processes. Each child of the shell starts a branch, and the executable that started the branch names it. `llama-server` is llama.cpp, `sd-server` stable-diffusion.cpp, `audiocpp_server` audio.cpp, `api`, `worker` or `python*` the backend, and anything else the interface. Naming the branch rather than each process is what files a router's model worker under llama.cpp, and a venv's interpreter under the launcher that started it. Without the variable, as when the API runs alone, the API's own process is the root.

The process table comes from psutil's `_ppid_map()`, the one snapshot its own `children()` is built on. Measured on Windows: 26 ms, where `process_iter(["ppid"])` took 13 s cold and 290 ms warm. It is private upstream, so a unit test fails if a psutil bump drops it; the fallback is `process_iter`. A process born before its listed parent is left out: Windows keeps a dead parent's pid as the child's ppid, and that pid can since belong to one of ours.

A whole sample took about 40 ms on the Windows test machine with its CPU saturated, most of it the process snapshot.

## What each figure is

| Figure | Source | Note |
|---|---|---|
| CPU | `psutil.cpu_percent()`, and each process's `cpu_percent()` divided by the logical cores | A rate against the previous sample, so the sampler keeps its `Process` objects between requests. A new process reads 0 for one sample. |
| RAM | `total - available` from `psutil.virtual_memory()`, and each process's resident size | Resident size is Task Manager's working set. Private bytes over-state: llama-server holding a model read 1,161 MB resident and 6,174 MB private. Shared libraries are counted once per process, so the app's sum is capped at what is in use. |
| VRAM | The platform's graphics reader | Dedicated memory only. |
| GPU | The platform's graphics reader | The busiest engine, as Task Manager reads a card. |

Memory is shown in binary units, as Task Manager and Activity Monitor count it, so a 16 GiB machine reads 16.0 GB.

## Graphics readers

A reader returns one reading per card: name, total, used, busy percent, and per-process memory and busy where the platform can attribute them. Where it cannot, those are null and the panel says the app's share is not reported, never zero. A reader that fails to start or to read costs the graphics rows only, logged once.

- **Windows.** DXGI lists the adapters with their names, dedicated memory and LUIDs; the software renderer is skipped. The GPU performance counters Task Manager reads (`GPU Adapter Memory`, `GPU Process Memory`, `GPU Engine`) give usage per adapter and per process, keyed by LUID. They come from the display driver model, so NVIDIA, AMD and Intel all answer. The PDH query is built fresh for every sample, because a wildcard counter lists only the instances alive when it was added: a query kept open never sees llama-server again after it restarts. Utilization is a rate, so each engine's raw reading is kept and paired with the next sample's, and the first sample reads it as unknown. A sample took 3 to 6 ms.
- **Linux.** NVIDIA through NVML (`libnvidia-ml.so.1`, shipped with the driver), with per-process memory from its compute and graphics process listings. AMD through amdgpu's sysfs files (`mem_info_vram_*`, `gpu_busy_percent`), with per-process memory from DRM fdinfo, read only for the app's own processes and only for descriptors open on `/dev/dri`.
- **macOS.** `ioreg -c IOAccelerator` gives the GPU's busy percent and the memory it has in use. Apple Silicon's memory is system RAM, so the reading is unified: the panel shows the GPU's load and no VRAM row, and the RAM row already holds the GPU's memory.

On every platform a card with under 1 GiB of its own memory is not listed: that is an integrated part's reservation (Intel's 128 MB, a Ryzen APU's 512 MB default), not memory a model is placed in.

## The panel

Three headed sections. **This computer** has one row each for CPU, RAM, and each card's VRAM and GPU load. A bar is split into the app's share (`chart-1`), other apps (`chart-3`) and free, and beside it are the machine's figure and the app's. RAM or VRAM at 90% or more turns the machine figure amber. Each bar is a `meter` whose value text is the whole reading as a sentence. **By engine** is a table of each engine's CPU, RAM and VRAM, with "Not running" for a runtime that is not up. **Graphics** names each card with its own memory, or says it shares the CPU's; with two or more it carries the same "GPU 1", "GPU 2" as the rows, so a name can be matched to its bars. A machine with no listed card has no Graphics section.

It polls every 2 seconds through TanStack Query, which stops while the window is hidden. The settings dialog mounts only the open section, so the query runs only while Resources is showing.

## Known gaps

- The Linux and macOS readers are covered by unit tests against recorded output, and have not been run on those systems.
- Intel's discrete cards on Linux (`xe`, `i915`) are not read, so they show no graphics rows.
- Per-process GPU load is read only on Windows. Linux and macOS show the card's load without the app's share.
