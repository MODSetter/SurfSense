---
status: proposed
code:
  - docker/surfsense/
  - surfsense_local/headless/
  - surfsense_local/runtimes/fetch-llamacpp.mjs
  - surfsense_local/runtimes/sdcpp/
  - .github/workflows/docker-surfsense.yml
---

# GPU images

> The Docker image comes in a CPU variant and one CUDA variant, `-cuda`, on CUDA 12.8; a `-cuda13` variant follows with arm64. llama.cpp comes from upstream's release builds; sd.cpp and audio.cpp come from the desktop's own recipes, so each runtime has one source for the desktop and the image. On a GPU image, chat and image generation run on the card; parsing, embeddings and voice stay on the CPU. Part of the [Docker proposal](README.md); the decisions are [ADR 0035](../../adr/0035-docker-compose-runs-the-desktop-stack.md) and [ADR 0073](../../adr/0073-the-docker-gpu-image-is-one-cuda-12-8-variant-from-upstream-builds.md).

The desktop app ships Vulkan and no CUDA because of installer size ([ADR 0012](../../adr/0012-vulkan-only-gpu-backend.md), [CUDA backend](../cuda-backend.md)). A Docker user pulls only the variant they ask for, so that constraint does not apply here.

## Variants

| Tag | CUDA | amd64 | arm64 | GPUs |
|---|---|---|---|---|
| `X.Y.Z`, `latest` | CPU | ✓ | later | none |
| `X.Y.Z-cuda`, `latest-cuda` | 12.8 | ✓ | — | Maxwell (GTX 900) to Blackwell (RTX 50) |
| `X.Y.Z-cuda13`, `latest-cuda13` | 13.3 | later | later | Turing (RTX 20) to Blackwell |

- **`-cuda` is the GPU image.** CUDA 12.8 covers every NVIDIA card CUDA 12 supports, Blackwell included, so on amd64 a CUDA 13 image adds only a newer driver floor.
- **`-cuda13` comes with arm64.** Upstream's only arm64 CUDA build of llama.cpp is 13.3, so one variant name covers arm64 boards (Jetson, Grace) and amd64 hosts that want CUDA 13. CUDA 13 drops Maxwell, Pascal and Volta and needs the R610 driver branch, so `-cuda` stays the default.
- **No `-cuda126`.** The legacy image had it for GPU torch, whose cu126 wheels serve older drivers ([`docker-build.yml`](https://github.com/MODSetter/SurfSense/blob/legacy/.github/workflows/docker-build.yml) on `legacy`). Here torch stays on the CPU, and upstream ships no CUDA 12.6 llama.cpp, so the variant would compile llama.cpp and sd.cpp on every release for hosts on drivers 560 to 569. A legacy self-hoster with `SURFSENSE_VARIANT=cuda126` sets `cuda`.

## What runs on the GPU

| Component | CPU image | CUDA image | Why |
|---|---|---|---|
| llama-server, chat | CPU | CUDA | the main gain |
| sd-server, images | CPU | CUDA | a large gain; generation is slow on a CPU |
| Docling, parsing | CPU | CPU | GPU torch adds about 3 GB of wheels; a later variant if parsing speed matters |
| bge-small, embeddings | CPU | CPU | small, and in process on the CPU ([ADR 0007](../../adr/0007-bundled-embeddings.md)) |
| audiocpp, voice | CPU | CPU | faster than real time on a CPU, and the card belongs to the chat model ([local audio models](../local-audio-models.md)) |

## Where each runtime comes from

One source per runtime, shared with the desktop: what the desktop takes from upstream, the image takes from upstream at the same pin; what the desktop builds, the image builds with the same recipe.

| Variant | llama.cpp at `b11050` | sd.cpp at `master-869-07a85c7` | audio.cpp at `v0.8.2` |
|---|---|---|---|
| desktop, Linux | downloaded: `…-ubuntu-vulkan-x64.tar.gz` | built by us, `vulkan` | built by us, CPU |
| CPU, amd64 | downloaded: `llama-b11050-bin-ubuntu-x64.tar.gz` | built by us, `cpu` | the desktop's build |
| `-cuda`, amd64 | downloaded: `llama-b11050-bin-ubuntu-cuda-12.8-x64.tar.gz` | **built by us, `cuda`**, CUDA 12.8.2 | the desktop's build |
| CPU, arm64 (later) | downloaded: `llama-b11050-bin-ubuntu-arm64.tar.gz` | built by us, `cpu` | built by us, CPU |
| `-cuda13` (later) | downloaded: `llama-b11050-bin-ubuntu-cuda-13.3-<arch>.tar.gz` | built by us, `cuda`, CUDA 13.3 | built by us, CPU |

"Downloaded" is upstream's release build; "built by us" is the desktop's recipe in `runtimes/`. In `-cuda`, sd.cpp is the one GPU runtime built by us.

- **Our builds stay ours.** Upstream publishes a Linux CPU sd.cpp and a Linux CPU audio.cpp, but they differ from what the desktop ships and tests: upstream's audio.cpp builds every model family, ours only the curated ones, and upstream's sd.cpp takes other flags. Taking them would put a second binary behind each feature, so a bug seen in one could not be reproduced in the other.
- **audio.cpp is the desktop's artifact.** Its Linux build is already CPU-only (`-DENGINE_ENABLE_CUDA=OFF`, started with `--backend cpu`), so the image takes the tarball `build-audiocpp.yml` makes for the desktop release, and every variant runs the binary the desktop runs. A local `docker build` runs the same recipe. Voice stays on the CPU in `-cuda`, as on a desktop with an NVIDIA card.
- **sd.cpp is one recipe with three variants.** Upstream publishes no Linux CUDA build of sd.cpp, only Windows, so the CUDA variant has to be compiled in any case.
- **sd.cpp compiles for the GPUs llama.cpp covers.** Its CUDA build takes upstream llama.cpp's default architectures at `b11050` (`50`, `61`, `70`, `75` and `80` as PTX; `86`, `89` and `120a` as device code), so chat and images run on the same cards.
- **One CUDA version per image.** The compile runs in `nvidia/cuda:12.8.2-devel-ubuntu24.04`, the image upstream builds its CUDA 12.8 llama.cpp in, so one set of CUDA runtime libraries (cudart, cuBLAS) serves llama-server and sd-server. Only the binaries and those libraries reach the final image, which stays on plain Ubuntu 24.04; the host's driver comes in through the NVIDIA Container Toolkit.
- **Pins as on the desktop.** llama.cpp stays at the desktop's `b11050`, sd.cpp at its commit and audio.cpp at its tag; each download is pinned by SHA-256.
- **Flash attention.** Upstream's CUDA build does not set `GGML_CUDA_FA_ALL_QUANTS`. Its default kernels cover matching K and V types, which the `q8_0` KV cache the fit estimate selects is ([CUDA backend](../cuda-backend.md), Decisions); step 14 confirms it on a card.

### What `runtimes/` gains

The staging scripts know one Linux build today, the desktop's Vulkan one, so even the CPU image needs this, from step 7, when it first stages llama.cpp:

- [`fetch-llamacpp.mjs`](../../../surfsense_local/electron/scripts/fetch-llamacpp.mjs) pins only `ubuntu-vulkan-x64` for `linux-x64`, and its `checkConfiguration()` throws on any Linux asset without `vulkan`.
- [`sdcpp/recipe.mjs`](../../../surfsense_local/electron/scripts/sdcpp/recipe.mjs) compiles Linux with `-DSD_VULKAN=ON` and nothing else.

Each script takes a variant beside its target: `linux-x64` with `cpu` or `cuda`, and later `linux-arm64` and `cuda13`. A llama.cpp variant gets its own pinned asset and SHA-256; an sd.cpp variant gets its own CMake flags (`-DSD_CUDA=ON`, or neither for the CPU) in the same recipe. The Vulkan rule in `checkConfiguration()` covers the desktop's targets only. With no variant, a script stages the desktop's build as today, so the installers do not change. Without a CPU variant, the CPU image would carry Vulkan binaries and `libvulkan` only to fall back to the CPU.

## One backend per image

Each image carries only its own ggml backend: CPU, or CUDA, never CUDA and Vulkan together. With both loaded, one card is listed twice ([CUDA backend](../cuda-backend.md)); with one, the fit estimate's first-GPU rule ([`fit.md`](../../architecture/local-models/fit.md)) holds unchanged. `SURFSENSE_LOCAL_LLAMACPP_LIBRARY_DIR` points at that backend, so the fit probe sees the card's memory with no code change.

## The host

- **Linux:** the NVIDIA driver and the NVIDIA Container Toolkit. **Windows:** the NVIDIA driver and Docker Desktop on WSL2, which passes the card through.
- **Driver.** `-cuda` needs **570.26 or newer** on Linux and **570.65 or newer** on Windows, CUDA 12.8's floors in [NVIDIA's release notes](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html). Driver 580, NVIDIA's last branch for Maxwell, Pascal and Volta, meets them. CUDA's minor version compatibility would let some 12.x drivers from 525 run it, but NVIDIA's own CUDA 12.8 images refuse those on GeForce cards, and so does this one.
- **One floor, kept beside the pin.** `runtimes/` holds the CUDA version with its Linux and Windows floors next to the llama.cpp asset it comes from, and a test fails if the asset's CUDA version and the floor's disagree. A bump that moves llama.cpp to a new CUDA changes the floor in the same commit; the installer, the image and the docs all read it.
- **The image enforces it.** The final image sets `NVIDIA_REQUIRE_CUDA=cuda>=12.8`, as NVIDIA's CUDA images do, so the NVIDIA Container Toolkit refuses to start it on an older driver, before anything runs. The image is plain Ubuntu, so nothing sets this unless it does.
- **The first run on an older card.** The driver compiles the PTX for Maxwell to Ampere on first use, which takes minutes, and caches it. The image sets `CUDA_CACHE_PATH=/data/cache/cuda`, so the cache survives an update instead of being rebuilt in every new container.
- **The image asks for compute only:** `NVIDIA_DRIVER_CAPABILITIES=compute,utility`.

## Choosing the variant

Compose and the image cannot see the host's card, so the variant is chosen before the container starts, in one of two ways.

- **The installer detects it.** `docker/scripts/install.sh` checks for a working `nvidia-smi`, for the NVIDIA Container Toolkit (`docker info`, `nvidia-ctk`) and for a driver at or above the pinned floor (`nvidia-smi --query-gpu=driver_version`), as the legacy installer's `host_has_nvidia_gpu`, `gpu_runtime_available` and `recommend_cuda_variant` do. With all three, it writes `SURFSENSE_VARIANT=cuda` and starts Compose with the GPU file. With a card but no toolkit, or a driver below the floor, it installs the CPU image and says what to update. `--gpu`, `--cpu`, `--variant=cpu|cuda` and `--gpu-count=N|all` override it.
- **By hand.** `SURFSENSE_VARIANT=cuda` in `.env`, and `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`; or `docker run --gpus all ghcr.io/modsetter/surfsense:latest-cuda`.

Users pull the published images; building one (`--build-arg VARIANT=cuda`) is for contributors.

## A CUDA image with no GPU

A container started without `--gpus` or the toolkit sees no card, and ggml falls back to the CPU silently. That is the most common GPU mistake in Docker, and it looks like a slow app.

On a CUDA image the headless entry's `headless/gpu-check.ts` runs `llama-server --list-devices` before boot. With no CUDA device it **refuses to start**, naming the fix: the toolkit, and the `gpus` or `deploy.resources` setting. `SURFSENSE_ALLOW_CPU=1` starts it anyway on the CPU.

## Compose

`docker/surfsense/docker-compose.gpu.yml`, layered on the main file as the legacy [`docker-compose.gpu.yml`](https://github.com/MODSetter/SurfSense/blob/legacy/docker/docker-compose.gpu.yml) is:

```yaml
services:
  surfsense:
    deploy:
      resources:
        reservations:
          devices:
            - driver: ${SURFSENSE_GPU_DRIVER:-nvidia}
              count: ${SURFSENSE_GPU_COUNT:-1}
              capabilities: [gpu]
```

with `SURFSENSE_VARIANT=cuda` in `.env`.

## CI

Two builds on amd64, CPU and `-cuda`, by digest. Both take audio.cpp from the `build-audiocpp.yml` artifact, so neither compiles it. With arm64, the CPU image gains an arm64 build merged into its manifest, and `-cuda13` builds on both architectures; a release then requires every architecture of every variant, as [`docker-build.yml`](https://github.com/MODSetter/SurfSense/blob/legacy/.github/workflows/docker-build.yml) on `legacy` does. Each variant moves `latest-<variant>` when the release is published, as the CPU image moves `latest` ([releases](README.md#releases)).

- sd.cpp's compile is the slow step, CPU and CUDA. It keeps its own registry cache per variant and architecture, so it reruns only when the sd.cpp pin or its flags change.
- The smoke job runs the CPU image only. GitHub's runners have no NVIDIA card, so the CUDA image is checked to start with `SURFSENSE_ALLOW_CPU=1` and to refuse without it; running it on a real card is a release checklist step.

## Steps

These continue the [Docker proposal's steps](README.md#steps), after the CPU image ships.

12. `-cuda` on amd64: llama.cpp from upstream's CUDA 12.8 build, sd.cpp's `cuda` variant, the GPU override file and `CUDA_CACHE_PATH`.
13. The no-GPU refusal.
14. On real hardware: a chat turn and an image on `-cuda`, on an RTX 30 or newer and on a GTX 10 or RTX 20 card, one of them on a driver at the floor, with the fit estimate reading the card's memory and the `q8_0` KV cache on fused kernels; and the toolkit refusing the image on a driver below it.

**Later, with arm64:** the CPU image on arm64, and `-cuda13` on arm64 and amd64.

## Not in scope

- Vulkan, ROCm, SYCL or OpenVINO images, so AMD and Intel GPUs use the CPU image.
- Kepler and older NVIDIA cards, which CUDA 12 dropped.
- GPU torch for Docling.
- More than one GPU.
