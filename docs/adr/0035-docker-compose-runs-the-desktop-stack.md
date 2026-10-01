# ADR 0035: The desktop app's stack also ships as one Docker container, with Caddy as its only listener

- **Status:** Accepted
- **Date:** 2026-10-01
- **Supersedes:** [ADR 0004](0004-desktop-app-is-its-own-tree.md) in part: Docker Compose leaves its out-of-scope list, and its loopback rule is narrowed to the API. [ADR 0012](0012-vulkan-only-gpu-backend.md) in part: Docker images may carry CUDA.
- **Source:** [Docker proposal](../proposals/docker/README.md), [GPU images](../proposals/docker/gpu.md)

## Context

The legacy self-host stack is `surfsense_backend` and `surfsense_web` with Postgres, Redis, Zero, SearxNG and OpenSandbox, built by [`docker-build.yml`](../../.github/workflows/docker-build.yml). Product direction is the desktop app, and self-hosters need a way to run it on a server, which ADR 0004 ruled out. ADR 0004 also kept the API on `127.0.0.1` because nothing authenticates a request, and binding it wider would make connection URLs an SSRF boundary.

## Decision

- `surfsense_local` ships as a Docker image and a Compose file, beside the desktop app. It is the same tree and the same code, not a fork.
- One container per install. A supervisor shared with Electron runs the API, the workers and the model servers, all on `127.0.0.1`, over one `/data` volume.
- Caddy, in the same container, is the only listener. It serves the frontend, proxies the API under `/api`, and refuses `/internal/*`.
- With no password set, Caddy answers only requests addressed to `localhost`, `127.0.0.1` or `[::1]`. With `SURFSENSE_PASSWORD` set, it answers the configured hosts behind basic auth, over HTTPS when a domain is set.
- Still one user per install: no accounts, as ADR 0004 says.
- The license is the same offline Keygen file as the desktop app ([ADR 0019](0019-offline-licenses.md)).
- Images come in a CPU variant and CUDA variants named as the legacy backend's are (`-cuda`, `-cuda126`). The desktop app stays Vulkan-only.
- Studio's model-written code runs in the worker as on the desktop ([ADR 0028](0028-model-written-code-runs-with-approval.md)); the container is the only boundary added.

## Consequences

- ADR 0004's other choices stand: SQLite, Huey, no accounts, no multi-seat LAN. One container is what keeps them true, since the database, the queue, the event broker and `/internal/events` all assume one machine.
- The API still never binds beyond loopback, in any mode.
- The legacy self-host compose can be retired once the new one ships. The license and scraper API backend in `surfsense_backend` is not part of this and stays.
- Nothing hosted is removed before the purge on 18 Oct 2026.
- A CUDA image is several GB larger than the CPU one, and its builds compile sd.cpp, and llama.cpp where upstream ships no binary.
- A fork can strip the license check, as it can on the desktop; enforcement stays server-side at the scraper API.

## Where the code stands

Nothing is built. The proposal's steps are the work.
