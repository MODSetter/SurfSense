# ADR 0012: The GPU backend is Vulkan everywhere off Apple Silicon, with no CUDA payload

- **Status:** Accepted
- **Date:** 2026-09-19
- **Source:** [llama.cpp runtime plan L47](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/07-llamacpp-runtime.md#L47), [CUDA backend plan L44–57](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/08-cuda-backend.md#L44-L57)

## Context

llama.cpp publishes a separate build per GPU backend. Off Apple Silicon a user's GPU may be NVIDIA, AMD or Intel. CUDA serves NVIDIA only and adds 685 MB on top of the Vulkan build. Measured on an RTX 3050 at llama.cpp `b11050`, CUDA leads Vulkan by 9.1% on `pp512`, 10.2% on `pp8192` and 2.1% on decode, which is 0.66 s on an 11 s turn. Packaging as built is in [packaging](../architecture/packaging.md).

## Decision

- macOS on Apple Silicon ships llama.cpp's arm64 build, which runs on Metal. Windows x64 and Linux x64 ship the Vulkan build. No CUDA payload ships.
- [`electron/scripts/fetch-llamacpp.mjs`](../../surfsense_local/electron/scripts/fetch-llamacpp.mjs) pins the build and each archive's SHA-256, and refuses to stage if any target other than macOS is not the Vulkan build.
- CUDA stays a deferred proposal ([`proposals/cuda-backend.md`](../proposals/cuda-backend.md)): not yet, revisited on new evidence rather than on a schedule.

## Consequences

- One 31 MB Vulkan archive covers NVIDIA, AMD and Intel, and its loader ships with Windows.
- NVIDIA users run on Vulkan and give up the measured gap above.
- Adding CUDA later needs no application code. ggml picks a backend by the library files present, so it is a change to the fetch script and a rebuild.
- A quantized KV cache needs flash attention, and Vulkan's vendor-neutral path for it is the less mature one. The CUDA proposal records this as the one argument for CUDA that has grown stronger.
- The Linux build runs on a pinned `ubuntu-22.04`, because a newer runner would raise the AppImage's glibc floor and llama.cpp's Vulkan build needs 2.34 ([`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml)).
