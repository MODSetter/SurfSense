---
status: proposed
code:
  - docker/local/
  - surfsense_local/electron/src/headless/
  - surfsense_local/electron/scripts/fetch-llamacpp.mjs
  - surfsense_local/electron/scripts/sdcpp/
  - .github/workflows/docker-local.yml
---

# GPU images

> The Docker image comes in a CPU variant and two CUDA variants with the legacy backend's names, `-cuda` for CUDA 12.8 and `-cuda126` for 12.6. On a GPU image, chat and image generation run on the card; parsing, embeddings and voice stay on the CPU. Part of the [Docker proposal](README.md); the decision is [ADR 0035](../../adr/0035-docker-compose-runs-the-desktop-stack.md).

The desktop app ships Vulkan and no CUDA because of installer size ([ADR 0012](../../adr/0012-vulkan-only-gpu-backend.md), [CUDA backend](../cuda-backend.md)). A Docker user pulls only the variant they ask for, so that constraint does not apply here.

## Variants

| Tag suffix | CUDA | amd64 | arm64 |
|---|---|---|---|
| none | CPU | ✓ | ✓ |
| `-cuda` | 12.8 | ✓ | ✓ |
| `-cuda126` | 12.6 | ✓ | ✓ |

The names and versions are the legacy backend's ([`docker-build.yml`](../../../.github/workflows/docker-build.yml)), so a self-hoster moving over keeps their `SURFSENSE_VARIANT`. `-cuda126` is for hosts whose driver is too old for 12.8.

## What runs on the GPU

| Component | CPU image | CUDA image | Why |
|---|---|---|---|
| llama-server, chat | CPU | CUDA | the main gain |
| sd-server, images | CPU | CUDA | a large gain; generation is slow on a CPU |
| Docling, parsing | CPU | CPU | GPU torch adds about 3 GB of wheels; a later variant if parsing speed matters |
| bge-small, embeddings | CPU | CPU | small, and in process on the CPU ([ADR 0007](../../adr/0007-bundled-embeddings.md)) |
| audiocpp, voice | CPU | CPU | faster than real time on a CPU, and the card belongs to the chat model ([local audio models](../local-audio-models.md)) |

## Where each runtime comes from

At the pinned llama.cpp build, `b11050`, upstream publishes Linux builds for CPU (x64, arm64), CUDA 12.8 (x64), CUDA 13.3 (x64, arm64), Vulkan, ROCm 10.0, SYCL and OpenVINO, with matching `cudart` archives that carry the CUDA runtime and cuBLAS.

| Variant | llama.cpp | sd.cpp |
|---|---|---|
| CPU | upstream download | compiled, CPU |
| `-cuda`, amd64 | upstream download, with its `cudart` | compiled, `-DSD_CUDA=ON` |
| `-cuda`, arm64 | compiled, `-DGGML_CUDA=ON` | compiled, `-DSD_CUDA=ON` |
| `-cuda126` | compiled, `-DGGML_CUDA=ON` | compiled, `-DSD_CUDA=ON` |

- Compiling happens in an `nvidia/cuda:<version>-devel-ubuntu24.04` stage and needs no GPU on the runner. Only the built binaries and the CUDA runtime libraries reach the final image, which stays on plain Ubuntu 24.04; the host's driver comes in through the NVIDIA Container Toolkit.
- Every compiled build uses the commit the desktop pins, so a variant differs from the desktop only in its backend.
- `GGML_CUDA_FA_ALL_QUANTS` is on, so the `q8_0` KV cache the fit estimate selects gets fused kernels ([CUDA backend](../cuda-backend.md), Decisions).

## One backend per image

Each image carries only its own ggml backend: CPU, or CUDA, never CUDA and Vulkan together. With both loaded, one card is listed twice ([CUDA backend](../cuda-backend.md)); with one, the fit estimate's first-GPU rule ([`fit.md`](../../architecture/local-models/fit.md)) holds unchanged. `SURFSENSE_LOCAL_LLAMACPP_LIBRARY_DIR` points at that backend, so the fit probe sees the card's memory with no code change.

## A CUDA image with no GPU

A container started without `--gpus` or the toolkit sees no card, and ggml falls back to the CPU silently. That is the most common GPU mistake in Docker, and it looks like a slow app.

On a CUDA image the headless entry's `gpu-check.ts` runs `llama-server --list-devices` before boot. With no CUDA device it **refuses to start**, naming the fix: the toolkit, and the `gpus` or `deploy.resources` setting. `SURFSENSE_ALLOW_CPU=1` starts it anyway on the CPU.

## Compose

`docker/local/docker-compose.gpu.yml`, layered on the main file as the legacy [`docker-compose.gpu.yml`](../../../docker/docker-compose.gpu.yml) is:

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

with `SURFSENSE_VARIANT=cuda` or `cuda126` in `.env`.

## CI

Six builds: three variants on two architectures, by digest, merged per variant; a release requires both architectures of every variant, as [`docker-build.yml`](../../../.github/workflows/docker-build.yml) does.

- The CUDA compiles are the slow step. Each variant and architecture keeps its own registry cache, as today.
- The smoke job runs the CPU image only. GitHub's runners have no NVIDIA card, so a CUDA image is checked to start with `SURFSENSE_ALLOW_CPU=1` and to refuse without it; running it on a real card is a release checklist step.

## Steps

These continue the [Docker proposal's steps](README.md#steps), after the CPU image ships.

12. The `-cuda` variant on amd64, from the upstream download, and the GPU override file.
13. The no-GPU refusal.
14. The compiled builds: `-cuda` on arm64, `-cuda126`, and sd.cpp with CUDA. On real hardware, a chat turn and an image on each CUDA variant, with the fit estimate reading the card's memory.

## Open questions

- The minimum driver for each variant, from NVIDIA's compatibility table, for the docs.
- Whether to add a `-cuda13` variant, which upstream ships ready-made on both architectures, once a host needs it.

## Not in scope

- Vulkan, ROCm, SYCL or OpenVINO images.
- GPU torch for Docling.
- More than one GPU.
