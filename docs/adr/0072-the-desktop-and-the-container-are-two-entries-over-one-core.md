# ADR 0072: The desktop app and the Docker container are two entries over one core, and the supervisor and runtime staging leave `electron/`

- **Status:** Accepted
- **Date:** 2026-10-25
- **Source:** [Docker proposal, One core, two entries](../proposals/docker/README.md#one-core-two-entries)

## Context

[ADR 0035](0035-docker-compose-runs-the-desktop-stack.md) ships the desktop stack as one container, run by a supervisor shared with Electron. Since [#2215](https://github.com/MODSetter/SurfSense/pull/2215) that supervisor, boot and the watchers import only Node, but they live in `surfsense_local/electron/src/main/sidecars/`, and the pinned staging of llama.cpp, sd.cpp, audio.cpp and opencode lives in `electron/scripts/`. Nothing but review keeps an Electron import out of them, and an image built from `electron/` carries the desktop's code with it. Projects that keep a desktop app and a server for years split them the same way: Actual Budget (`loot-core`, `desktop-electron`, `sync-server`), Element (`apps/web`, `apps/desktop`) and Trilium (`apps/server`, `apps/desktop`).

## Decision

- `surfsense_local/` holds the core, `backend/`, `frontend/`, `sidecars/` and `runtimes/`, and two entries, `electron/` for the desktop and `headless/` for the container. Both entries call the same `bootSidecars`.
- `sidecars/` is today's `electron/src/main/sidecars/`, with `net.ts` and the session log's Node-only files. A test fails on any `electron` import under it.
- `runtimes/` is the staging scripts from `electron/scripts/`. Each takes a target and an output folder, and with neither stages for the host into `electron/<runtime>/`, so electron-builder and the packaged app do not change.
- `electron/` keeps the window, IPC, the keychain, the updater, the previews and packaging. `headless/` builds the boot context from the environment and adds Caddy, the GPU check and signal handling.
- The image's files live in `docker/surfsense/`, one folder per image as `docker/keygen/` is. Its build context is the repository root.
- Rejected: leaving the core in `electron/` with `electron/src/headless/` beside it. It needs no move, but the boundary stays a convention, and every image build depends on the desktop package.

## Consequences

- One pull request moves the folders, with no behaviour change, before the headless entry is written, so the entry lands in its final place.
- `desktop-tests.yml`, `build-audiocpp.yml`, `build-sdcpp.yml`, `release-local.yml` and `CODEOWNERS` follow the new paths. `release-local.yml` runs only on a tag, so the move is checked with its dry run before it merges, and the sd.cpp and audio.cpp caches rebuild once.
- Docs that link into `electron/src/main/sidecars/` or `electron/scripts/` are repointed in the same change.
- The image copies `surfsense_local/` without `electron/`, plus `backend/plugins/bundles/core/`, which the backend depends on.

## Where the code stands

The core and both entries are in place: [`sidecars/`](../../surfsense_local/sidecars/), [`runtimes/`](../../surfsense_local/runtimes/) and [`headless/`](../../surfsense_local/headless/). The staging scripts take no target or output folder yet; that comes with the image's runtimes, steps 7 to 9 of the [Docker proposal](../proposals/docker/README.md#steps). `docker/surfsense/` does not exist until step 5.
