---
status: proposed
code:
  - docker/local/
  - surfsense_local/electron/src/main/sidecars/
  - surfsense_local/electron/scripts/
  - surfsense_local/electron/src/main/index.ts
  - surfsense_local/electron/src/headless/
  - surfsense_local/backend/api/config.py
  - surfsense_local/backend/api/main.py
  - surfsense_local/frontend/src/lib/api.ts
  - .github/workflows/docker-local.yml
---

# Running SurfSense in Docker

> The desktop app's stack, minus Electron, as one container: a supervisor shared with Electron runs the API, the workers and the model servers on loopback, and Caddy is the only thing listening. It replaces the legacy self-host compose. The decision is [ADR 0035](../../adr/0035-docker-compose-runs-the-desktop-stack.md); GPU images are in [`gpu.md`](gpu.md).

## What changes

| | Legacy self-host | With this |
|---|---|---|
| Images | `surfsense-backend`, `surfsense-web`, `surfsense-sandbox` | `surfsense`, one image |
| Services | Postgres, Redis, Zero, SearxNG, OpenSandbox, Caddy, backend, two Celery processes, frontend | one |
| Accounts | yes | no: one user, as on the desktop |
| Models | remote providers | the desktop catalog: llama.cpp, sd.cpp, audio.cpp, plus remote connections |
| Data | Postgres and an object store | one `/data` volume, the desktop's `~/.surfsense` layout |
| License | none | the desktop's offline Keygen file |
| Port | `3929` | `3929` |

## The container

```text
surfsense container                         one port: 80, or 80 and 443 with a domain
├─ tini, PID 1
└─ supervisor (Node, shared with Electron)
   ├─ caddy             0.0.0.0:80/443, the only listener
   │    /           →   frontend/dist
   │    /api/*      →   127.0.0.1:<api>, prefix stripped
   │    /api/internal/*  →  403
   ├─ api               127.0.0.1:<free port>
   ├─ worker ingest, worker studio
   ├─ llama-server      127.0.0.1:<free port>
   ├─ audiocpp_server   once audio/server.json names a model
   └─ sd-server         once an image model is chosen
volume /data = SURFSENSE_LOCAL_DATA_DIR
```

One container, because the stack assumes one machine: SQLite and the Huey queue share a filesystem, the SSE broker is in memory, workers post to `/internal/events` on loopback ([`worker/notify.py`](../../../surfsense_local/backend/worker/notify.py)), and egress exempts only loopback. Split across containers, each of those breaks; in one, none changes.

## The supervisor, shared with Electron

The sidecar specs and the process supervisor in [`electron/src/main/sidecars/`](../../../surfsense_local/electron/src/main/sidecars/) already import only Node. What ties boot to Electron is in [`index.ts`](../../../surfsense_local/electron/src/main/index.ts): `bootSidecars()` reads `app.isPackaged` and `process.resourcesPath`, and the three watchers live beside it.

- Boot and the watchers move into `sidecars/`, taking their paths as a context instead of reading Electron. The watchers restart llama-server when `models/models.ini` changes, restart audiocpp when `audio/server.json` changes, and start or stop sd-server from `/llm/image/local/runtime`.
- `electron/src/headless/` is the container's entry. It builds that context from the environment, runs the start-up checks, boots, waits for `/health`, then starts Caddy as one more sidecar. It forwards SIGTERM to every child. Node 24 runs it as TypeScript, as the package's tests already run, so it has no build step.
- Electron keeps the window, the keychain, the updater and `shell`.
- The Python sidecars run from a venv in the image, not PyInstaller. [`python.ts`](../../../surfsense_local/electron/src/main/sidecars/python.ts) already runs `backendDir/.venv` outside a packaged build, so the headless context points `backendDir` at `/app/backend` and sets the packaged-only environment, such as `HF_HUB_OFFLINE`, itself.
- There is no shell entrypoint. The checks live in `headless/`, tested with `node:test` like the rest of the sidecar code; the image runs `tini -- node /app/electron/src/headless/main.ts`.

One implementation means a fix to sidecar handling lands in both.

## Files

The new stack, in `docker/local/`:

| Path | Holds |
|---|---|
| `Dockerfile` | every variant; `ARG VARIANT` picks the runtimes stage |
| `Dockerfile.dockerignore` | the ignore list, which BuildKit reads beside the Dockerfile |
| `docker-compose.yml` | the service |
| `docker-compose.gpu.yml` | the GPU device reservation, layered on top |
| `.env.example` | version, variant, port, password, hosts, domain |
| `caddy/Caddyfile` | the routes; imports one access file |
| `caddy/access-local.caddy` | access without a password, for `localhost` hosts only |
| `caddy/access-password.caddy` | `basic_auth` and the allowed hosts |
| `scripts/` | later: `install.sh` and `install.ps1` for this stack |

The code, in `surfsense_local/`:

| Path | Holds |
|---|---|
| `electron/src/main/sidecars/boot.ts` | boot, moved out of `index.ts`, with its paths as a context |
| `electron/src/main/sidecars/watch-generation-preset.ts` | restarts llama-server when `models.ini` changes |
| `electron/src/main/sidecars/watch-audio-models.ts` | restarts audiocpp when `server.json` changes |
| `electron/src/main/sidecars/watch-image-model.ts` | starts, restarts or stops sd-server for the selected image model |
| `electron/src/headless/main.ts` | the container's entry: checks, boot, `/health`, Caddy, signals |
| `electron/src/headless/context-from-env.ts` | the `/data` and `/app` paths and the secret |
| `electron/src/headless/caddy.ts` | Caddy as a `SidecarSpec`; hashes the password |
| `electron/src/headless/gpu-check.ts` | the no-GPU refusal ([`gpu.md`](gpu.md)) |
| `electron/scripts/` | runtime staging, extended for the image's targets |
| `backend/api/config.py` | `SURFSENSE_LOCAL_CORS_ORIGINS` |
| `frontend/src/lib/api.ts` | the `VITE_API_BASE` fallback |

CI is `.github/workflows/docker-local.yml`.

- **Every file of the new stack is in `docker/local/`, and nothing outside it in `docker/` changes.** The new stack reads nothing from the legacy files and the legacy stack reads nothing from `docker/local/`, so either can change or be deleted without touching the other.
- **`docker/local/`, not the top of `docker/`.** [`install.sh`](../../../docker/scripts/install.sh) downloads `docker/docker-compose.yml`, `docker/.env.example`, `docker/proxy/Caddyfile` and five more by path from `main`, so a new file at any of those paths reaches every legacy install. The folder name is fixed from the start, because this stack's own install script will be fetched by its path too. Retiring the legacy stack deletes its files and leaves `docker/local/` where it is.
- **Code stays in its tree.** `docker/local/` holds only what Docker reads; the supervisor, the checks and the settings are application code in `surfsense_local/`.
- **Runtime staging is shared.** The Dockerfile runs the desktop's pinned fetch and compile scripts with the image's targets, so the pins cannot drift between the two.

Inside the image:

| Path | Holds |
|---|---|
| `/app/backend/` | the source and its `.venv` |
| `/app/frontend/dist/` | built with `VITE_API_BASE=/api` |
| `/app/electron/src/` | `sidecars/`, `headless/`, `session-log/` |
| `/app/runtimes/` | `llamacpp/`, `sdcpp/`, `audiocpp/`: one GPU backend per variant |
| `/app/models/` | bge-small, the Docling pack, Kokoro |
| `/data/` | the volume |

## Caddy and access

| Setting | Caddy answers | Auth |
|---|---|---|
| Default | `Host` of `localhost`, `127.0.0.1` or `[::1]` only | none, as on the desktop |
| `SURFSENSE_PASSWORD` | the hosts in `SURFSENSE_ALLOWED_HOSTS`, or any | `basic_auth` |
| `SURFSENSE_DOMAIN` also | that domain | `basic_auth`, over HTTPS |

- **The `Host` check is the guard.** The container cannot see how Compose published its port, but it sees the address each request was sent to. Without a password, a request to the LAN address or a domain is refused, so an unauthenticated instance cannot be reached from the network by accident. The same check stops DNS rebinding against `localhost`.
- **The password is hashed at start.** The headless entry runs `caddy hash-password` on `SURFSENSE_PASSWORD`, so nobody handles a bcrypt string. The SPA, the API and the SSE streams are one origin, so the browser sends the credentials on all of them.
- **HTTPS.** A public domain gets an automatic certificate; `SURFSENSE_TLS=internal` uses Caddy's own CA on a LAN.
- **`/api/internal/*` is refused.** Workers reach `/internal/events` on loopback and never through Caddy.
- **CORS.** The API answers `*` today, because the desktop renderer loads from `file://` ([`api/main.py`](../../../surfsense_local/backend/api/main.py)). The allowed origins come from `SURFSENSE_LOCAL_CORS_ORIGINS`, defaulting to `*` for the desktop. The image sets it empty: everything is same-origin, so no other site can read a response.
- **Streaming.** Caddy flushes `text/event-stream` responses immediately, so chat and live updates stream unchanged. It sets no body limit; uploads stay capped by the API at 500 MB.
- **Behind the user's own proxy**, leave `SURFSENSE_DOMAIN` empty, set the password, and point the proxy at port 80.

## The frontend without Electron

Every bridge call is already optional (`window.surfsense?.…`). The build for the image sets `VITE_API_BASE=/api`, and [`lib/api.ts`](../../../surfsense_local/frontend/src/lib/api.ts) reads `window.surfsense?.apiUrl ?? import.meta.env.VITE_API_BASE ?? ""`.

| Desktop | In Docker |
|---|---|
| Open, Show in folder | download through `GET .../documents/{id}/original`; PDFs preview in the app ([source preview](../source-preview.md)) |
| electron-updater | hidden; updating is pulling a newer tag |
| Keychain secret ([ADR 0018](../../adr/0018-keychain-envelope-encryption.md)) | `SURFSENSE_LOCAL_SECRET` from the environment, else the `DATA_DIR/secret` file [`shared/secrets.py`](../../../surfsense_local/backend/shared/secrets.py) already falls back to |
| Session log, About details, crash toast | hidden |
| Theme, locale, external links | the browser fallbacks that exist |

## Data and license

- `/data` holds what `~/.surfsense` holds: `surfsense.db`, `huey.db`, `models/`, `images/`, `audio/`, `data/workspaces/`, `plugins/`, `imports/`. Backing up is copying the volume.
- Migrations run when the API starts ([ADR 0005](../../adr/0005-hand-written-migrations.md)); workers never migrate.
- The license is a file in `/data`, verified offline with the keys built into the image. It has no machine binding ([ADR 0019](../../adr/0019-offline-licenses.md)), so the same file works on a desktop and a server, and it gates the same things.

## The image

`docker/local/Dockerfile`, context `surfsense_local/`, on Ubuntu 24.04: the upstream llama.cpp and sd.cpp Linux builds need a recent glibc.

| Stage | Produces |
|---|---|
| `frontend` | `pnpm build` with `VITE_API_BASE=/api` |
| `backend` | `uv sync` into `/app/.venv`; torch from the CPU index, as [`pyproject.toml`](../../../surfsense_local/backend/pyproject.toml) pins on Linux |
| `runtimes` | llama.cpp, sd.cpp and audio.cpp with eSpeak, staged by the desktop's own pinned fetch and build scripts |
| `models` | bge-small, the Docling parser pack and Kokoro, by the desktop's fetch scripts |
| `headless` | the supervisor entry |
| `runtime` | the above, Node, Caddy and tini |

- `linux/amd64` and `linux/arm64`.
- Several GB: torch and Docling, plus about 1 GB of bundled models. Generation weights download at run time into `/data`, as on the desktop.
- `HEALTHCHECK` calls `/health` through loopback.

## Compose

`docker/local/docker-compose.yml`:

```yaml
services:
  surfsense:
    image: ghcr.io/modsetter/surfsense:${SURFSENSE_VERSION:-latest}${SURFSENSE_VARIANT:+-${SURFSENSE_VARIANT}}
    ports:
      - "${SURFSENSE_BIND:-127.0.0.1}:${SURFSENSE_PORT:-3929}:80"
    volumes:
      - surfsense_data:/data
    environment:
      SURFSENSE_PASSWORD: ${SURFSENSE_PASSWORD:-}
      SURFSENSE_ALLOWED_HOSTS: ${SURFSENSE_ALLOWED_HOSTS:-}
      SURFSENSE_DOMAIN: ${SURFSENSE_DOMAIN:-}
    restart: unless-stopped
volumes:
  surfsense_data:
```

A GPU override file sits beside it ([`gpu.md`](gpu.md)).

## CI

A new workflow, `docker-local.yml`. [`docker-build.yml`](../../../.github/workflows/docker-build.yml) stays on `v0.*` for the legacy images until they are retired.

- Runs on the desktop's release tags, `v[1-9]*`, and on `dev` pushes that touch `surfsense_local/**` or `docker/local/**`.
- The same shape as today: build by digest per architecture and variant, require both architectures on a release, merge into one manifest.
- Tags: the version, `latest`, the branch, `git-<sha>`, each with the variant suffix.
- A smoke job starts the CPU image, waits for `/health` through Caddy, and checks that a non-local `Host` is refused without a password.

## Leaving the legacy stack

1. **Now:** the new image ships beside the legacy one, and both are documented.
2. **After 18 Oct 2026:** the root README points self-hosters at the new compose, and the legacy compose is marked deprecated.
3. **Later:** `surfsense-web`, `surfsense-sandbox` and the self-host services leave CI and `docker/`. The license and scraper API backend stays.

A legacy self-hoster moves their data with the markdown export and import ([ADR 0022](../../adr/0022-markdown-only-cloud-import.md)).

## Steps

1. Move boot and the watchers into `sidecars/` with no Electron import; Electron uses them unchanged.
2. The headless entry with its checks, the configurable CORS origins and `VITE_API_BASE`.
3. The Dockerfile, the Caddy files and the Compose file: CPU only.
4. `docker-local.yml` with the smoke job.
5. The GPU variants ([`gpu.md`](gpu.md)).
6. Docs: a `docker.md` in `architecture/`, and the root README.

## Not in scope

- Accounts, several users, several API replicas.
- A sandbox for Studio's model-written code beyond the container.
- The plugins worker, which Electron does not start yet either.
- A Vulkan or ROCm image for AMD and Intel GPUs.
