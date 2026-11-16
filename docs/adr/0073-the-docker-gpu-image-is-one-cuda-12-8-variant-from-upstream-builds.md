# ADR 0073: The Docker GPU image is one CUDA 12.8 variant, with `-cuda13` to follow for arm64, and each runtime has one source shared with the desktop

- **Status:** Accepted
- **Date:** 2026-10-25
- **Supersedes:** [ADR 0035](0035-docker-compose-runs-the-desktop-stack.md) in part: its CUDA variants named as the legacy backend's (`-cuda`, `-cuda126`).
- **Source:** [GPU images](../proposals/docker-gpu.md)

## Context

ADR 0035 gave the Docker image the legacy backend's CUDA variants, `-cuda` for CUDA 12.8 and `-cuda126` for 12.6. The legacy variants picked PyTorch wheels, `cu128` and `cu126`, because the legacy backend ran torch on the GPU, and PyTorch's cu126 wheels serve older drivers. In the new image torch stays on the CPU; only llama.cpp and sd.cpp use the card.

At the desktop's pins, upstream llama.cpp (`b11050`) publishes Linux builds for CPU (x64, arm64), CUDA 12.8 (x64) and CUDA 13.3 (x64, arm64), but none for 12.6. Upstream sd.cpp (`master-869-07a85c7`) and audio.cpp (`v0.8.2`) publish Linux CPU builds, but not the ones the desktop ships: the desktop compiles both from its own recipes, and sd.cpp publishes no Linux CUDA build at all. Upstream's CUDA 12.8 llama.cpp covers Maxwell to Blackwell; CUDA 13 drops Maxwell, Pascal and Volta.

## Decision

- The image comes in two variants: CPU, and `-cuda` on CUDA 12.8, both on amd64.
- `-cuda13`, on CUDA 13.3, follows with arm64, for arm64 boards and for amd64 hosts that want CUDA 13.
- There is no `-cuda126`.
- Each runtime has one source, shared with the desktop. llama.cpp comes from upstream's release builds at the desktop's pin in every variant. sd.cpp is compiled from the desktop's recipe, with a `cpu` and a `cuda` variant beside the desktop's `vulkan`; the CUDA one uses the CUDA version upstream builds llama.cpp with, for the GPU architectures upstream llama.cpp covers. audio.cpp is the desktop's own CPU-only build, in every variant.
- Rejected: upstream's Linux CPU builds of sd.cpp and audio.cpp. They would spare a compile but put a second binary behind each feature.
- Rejected: keeping `-cuda126` for the legacy names. It would compile llama.cpp and sd.cpp on every release to serve hosts on drivers 560 to 569 with a card older than an RTX 30.

## Consequences

- A release compiles sd.cpp once per variant, and one of those is CUDA; audio.cpp comes from the desktop release's artifact.
- Hosts need CUDA 12.8's driver floor for `-cuda`, 570.26 on Linux and 570.65 on Windows, which the image enforces through `NVIDIA_REQUIRE_CUDA`. A host that cannot reach it runs the CPU image.
- A legacy self-hoster with `SURFSENSE_VARIANT=cuda126` changes it to `cuda`.
- Older cards compile PTX on their first run, so the image keeps the driver's cache in `/data`.
- Voice runs on the CPU in every variant, as on the desktop.

## Where the code stands

Nothing is built. The variants are steps 12 to 14 of the [GPU images proposal](../proposals/docker-gpu.md#steps).
