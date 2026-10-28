# Docker

The desktop app's stack without Electron, as one container, `ghcr.io/modsetter/surfsense`. `surfsense_local` is one core with two entries: Electron for the desktop, a headless Node entry for the container. The headless entry runs the same supervisor as Electron, which starts the API, the workers, the model servers and opencode on loopback; Caddy is the only thing listening. It replaces the legacy self-host compose, which lives on the `legacy` branch ([legacy split](../proposals/legacy-split/README.md)). Who can open it, and how, is [Docker access](docker-access.md); GPU images are a [proposal](../proposals/docker-gpu.md).

**Code:** [`docker/surfsense/`](../../docker/surfsense/), [`surfsense_local/headless/`](../../surfsense_local/headless/), [`surfsense_local/sidecars/`](../../surfsense_local/sidecars/), [`surfsense_local/runtimes/`](../../surfsense_local/runtimes/), [`docker-tests.yml`](../../.github/workflows/docker-tests.yml), [`release-docker.yml`](../../.github/workflows/release-docker.yml)
**Decisions:** [ADR 0035](../adr/0035-docker-compose-runs-the-desktop-stack.md), [ADR 0072](../adr/0072-the-desktop-and-the-container-are-two-entries-over-one-core.md), [ADR 0074](../adr/0074-docker-sign-in-is-a-surfsense-page-that-caddy-enforces.md), [ADR 0075](../adr/0075-what-differs-in-docker-is-gated-by-one-build-flag-or-the-bridge.md)

| | Legacy self-host | This image |
|---|---|---|
| Images | `surfsense-backend`, `surfsense-web`, `surfsense-sandbox` | `surfsense`, one image |
| Services | Postgres, Redis, Zero, SearxNG, OpenSandbox, Caddy, backend, two Celery processes, frontend | one |
| Accounts | yes | one password, no accounts: one user, as on the desktop |
| Models | remote providers | the desktop catalog: llama.cpp, sd.cpp, audio.cpp on the CPU, plus remote connections |
| Data | Postgres and an object store | one `/data` volume, the desktop's `~/.surfsense` layout |
| License | none | the desktop's offline Keygen license |
| Port | `3929` | `4929`, so both can run side by side while data moves over |
| Updates | Watchtower or a manual pull | pulling a newer tag; no in-app updater |

## The container

```text
surfsense container                 ports 80, and 443 with HTTPS
├─ tini -g, PID 1
└─ node headless/main.ts
   ├─ access service    127.0.0.1:<free port>   who may in (headless/access/)
   ├─ caddy             0.0.0.0:80/443, the only listener
   │    /access/*        →  the access service
   │    everything else  →  forward_auth to the access service first
   │    /api/*           →  127.0.0.1:<api>, prefix stripped
   │    /api/internal/*  →  403
   │    /plugins/oauth/callback, /plugins/oauth/client.json  →  the API
   │    /callback        →  ChatGPT's sign-in listener
   │    /                →  frontend/dist
   └─ bootSidecars      sidecars/boot.ts, the same call Electron makes
      ├─ api                     127.0.0.1:<free port>
      ├─ worker ingest, worker studio, worker plugins
      ├─ llama-server            127.0.0.1:<free port>
      ├─ audiocpp_server         once audio/server.json names a model
      ├─ audiocpp transcription  once audio/transcription.json names a model
      ├─ sd-server               while a Studio image job runs, and 5 minutes after
      └─ opencode, its proxy     once agent/opencode.json exists
volume /data = SURFSENSE_LOCAL_DATA_DIR
```

One container, because the stack assumes one machine: SQLite and the Huey queue share a filesystem, the SSE broker is in memory, workers post to `/internal/events` on loopback ([`worker/notify.py`](../../surfsense_local/backend/worker/notify.py)), and egress exempts only loopback. Split across containers, each of those breaks; in one, none changes.

| Network | What is on it | Who reaches it |
|---|---|---|
| The container's loopback | the API, the workers, the model servers, opencode and the access service, each on a free port | processes in the container only |
| Compose's default bridge | the container's interface, with only Caddy listening, on `:80` and `:443` | the host, through the published ports |
| The published ports | `${SURFSENSE_BIND:-0.0.0.0}:${SURFSENSE_PORT:-4929}` → `80`, and `${SURFSENSE_HTTPS_PORT:-4943}` → `443` | every network the server is on, behind the password; the host alone with `SURFSENSE_BIND=127.0.0.1` |
| Outbound | NAT through the bridge | remote providers, model downloads and the plugin host, under the backend's egress rules |

- **No container talks to another,** and every call stays on loopback.
- **Docker's published ports pass the host's firewall,** `ufw` included, so a server reachable from the internet presets `SURFSENSE_PASSWORD` before its first start ([Docker access](docker-access.md#the-first-password)).
- **No Docker socket.** The container needs nothing from the host but the volume.

## One core, two entries

`surfsense_local` is split by what runs where, as Actual Budget, Element and Trilium split theirs ([ADR 0072](../adr/0072-the-desktop-and-the-container-are-two-entries-over-one-core.md)):

```text
surfsense_local/
  backend/     core: the API and the workers (Python)
  frontend/    core: the UI (React)
  sidecars/    core: boot, the sidecar specs, the supervisor, the watchers, net, the session log
  runtimes/    core: the pinned staging of llama.cpp, sd.cpp, audio.cpp and opencode
  electron/    desktop entry: the window, IPC, the keychain, the updater, previews, electron-builder
  headless/    container entry: the context from the environment, Caddy, access, signals
```

- **`sidecars/` imports only Node.** A test, [`no-electron.test.ts`](../../surfsense_local/sidecars/no-electron.test.ts), fails on any `electron` import under it.
- **`runtimes/` is shared staging.** Each script takes `--out`, and llama.cpp's and sd.cpp's take `--variant cpu`, which the image stages; with neither, each stages the desktop's build into `electron/<runtime>/`, so the packaged app does not change.
- **`electron/` and `headless/` both call `bootSidecars`.** [`index.ts`](../../surfsense_local/electron/src/main/index.ts) builds its context from `app.isPackaged` and `process.resourcesPath`; [`context-from-env.ts`](../../surfsense_local/headless/context-from-env.ts) from the environment. A fix to sidecar handling lands in both.
- **Node 24 runs `sidecars/` and `headless/` as TypeScript**, with no build step. Each has its own `package.json` and `node:test` suite.

## The headless entry

[`headless/main.ts`](../../surfsense_local/headless/main.ts) does what `index.ts` does around boot, without a window:

1. **The context.** `context-from-env.ts` sets every `BootContext` field: `packaged: false`, the backend and runtime folders under `/app`, `dataDir` from `SURFSENSE_LOCAL_DATA_DIR` (default `/data`), and the models folder.
2. **The secret, before boot.** `SURFSENSE_LOCAL_SECRET`, else `/data/secret`, created once with mode 600 and never regenerated ([`secret.ts`](../../surfsense_local/headless/secret.ts)). Node settles it before any Python starts, so no two processes race to create it.
3. **The container's environment** ([`container-env.ts`](../../surfsense_local/headless/container-env.ts)): `HF_HUB_OFFLINE=1`, since the bundled models are in the image; `SURFSENSE_LOCAL_SIGNED_REGISTRY=1` (below); `SURFSENSE_LOCAL_RUNTIME=docker`, which the API reads as `in_container()`; and `HOME=/data/home`, so what a user installs in the container keeps across updates.
4. **Settings that stop it at start, saying why:** a `SURFSENSE_TLS` it cannot serve ([`tls-mode.ts`](../../surfsense_local/headless/tls-mode.ts)), and a `SURFSENSE_AUTH` other than empty or `none` ([`sign-in-mode.ts`](../../surfsense_local/headless/sign-in-mode.ts)).
5. **Boot and health.** `bootSidecars`, then `/health` within 60 s. Then, when `SURFSENSE_LOCAL_CADDYFILE` names a Caddyfile, as the image does, the access service and Caddy as one more sidecar; a checkout runs the API alone. Caddy gets the API's port, the access service's, the SPA's folder and a fixed port for ChatGPT's sign-in listener, given to the API as `SURFSENSE_LOCAL_CHATGPT_CALLBACK_PORT` ([`caddy.ts`](../../surfsense_local/headless/caddy.ts)); its exit ends the process non-zero, as the API's does. `/data/api-url` is written as on the desktop, so `surfsense-plugins invoke` works inside the container.
6. **The password.** `SURFSENSE_PASSWORD`, read once and deleted from the environment, sets it; without it, the log says how to create one ([Docker access](docker-access.md)).
7. **Signals and exit.** SIGTERM and SIGINT stop the watchers, then every child's process group. The API exiting stops the container with a non-zero code, so Compose's `restart:` applies; any other sidecar is restarted by the supervisor.

**The backend's packaged switch.** A venv backend reads `sys.frozen` as false, and [`registry_origin.reads_repository()`](../../surfsense_local/backend/modules/plugins/lists/registry/registry_origin.py) would then trust the checkout's unsigned plugin registry. `SURFSENSE_LOCAL_SIGNED_REGISTRY` makes it read the signed registry from the plugin host, as a packaged desktop does.

## Files

In `docker/surfsense/`:

| Path | Holds |
|---|---|
| `Dockerfile` | the image's stages, below |
| `Dockerfile.dockerignore` | the ignore list, which BuildKit reads beside the Dockerfile |
| `docker-compose.yml` | the service |
| `.env.example` | every setting, explained |
| `caddy/Caddyfile` | plain HTTP, the default |
| `caddy/Caddyfile.lan` | HTTPS on a LAN under Caddy's own certificate authority (`SURFSENSE_TLS=internal`) |
| `caddy/Caddyfile.domain` | HTTPS for a public domain, from Let's Encrypt (`SURFSENSE_DOMAIN`) |
| `caddy/routes.caddy` | the routes every Caddyfile imports |
| `caddy/access.caddy` | `forward_auth` to the access service, and its `/access/*` |
| `caddy/spa.caddy` | the SPA's route, last; the dev stack mounts its own |
| `dev/compose.yml`, `dev/spa.caddy` | the image with the checkout mounted in ([Developing the image](#developing-the-image)) |

- **The build context is the repository root.** The backend depends on `backend/plugins/bundles/core/manifest` and reads the plugin SDK from `backend/plugins/bundles/core/sdk`, so `surfsense_local/` alone cannot build it. The ignore list admits only `surfsense_local/` and those two folders.
- **`docker/surfsense/` holds only what Docker reads.** The supervisor, the access service and the settings' rules are application code in `surfsense_local/`.

Inside the image, the repository's layout under `/app`, so every relative path the backend resolves holds:

| Path | Holds |
|---|---|
| `/app/surfsense_local/backend/` | the source and its `.venv` |
| `/app/surfsense_local/frontend/dist/` | built with `VITE_API_BASE=/api` and `VITE_SURFSENSE_RUNTIME=docker` |
| `/app/surfsense_local/sidecars/`, `headless/` | the supervisor and the entry |
| `/app/runtimes/` | `opencode/`, `llamacpp/`, `sdcpp/` and `audiocpp/`, CPU builds |
| `/app/surfsense_local/backend/models/` | bge-small, the Docling parser pack, Silero VAD and the Kokoro voice |
| `/app/caddy/` | the Caddyfiles and what they import |
| `/app/backend/plugins/bundles/core/` | `manifest/` and `sdk/` |
| `/data/` | the volume |

## Caddy and access

Caddy is the one door in. A published port reaches the container's interface, never its loopback, so something must listen there and forward inward, and the API cannot be that: nothing authenticates it, and `/internal/events` is protected only by its loopback bind ([ADR 0035](../adr/0035-docker-compose-runs-the-desktop-stack.md)). Caddy also serves `frontend/dist`, which Electron loads from disk on the desktop, on the same origin as `/api`, holds HTTPS, and asks the access service about every request through `forward_auth` ([ADR 0074](../adr/0074-docker-sign-in-is-a-surfsense-page-that-caddy-enforces.md)). The password, the setup, sign-in turned off and every case are in [Docker access](docker-access.md).

- **HTTPS.** [`tls-mode.ts`](../../surfsense_local/headless/tls-mode.ts) picks the Caddyfile: plain HTTP by default; `SURFSENSE_TLS=internal` issues certificates for each name in `SURFSENSE_ALLOWED_HOSTS` from Caddy's own authority, whose root each device trusts once; `SURFSENSE_DOMAIN` gets one from Let's Encrypt. Plain HTTP on another address redirects to HTTPS on `SURFSENSE_HTTPS_PORT`. Over plain HTTP the password crosses the network in the clear, and browsers allow the microphone only in a secure context.
- **Three root paths reach the API besides `/api/*`:** the sign-in callbacks and the instance's client document ([Sign-ins](#sign-ins)), each matched exactly.
- **`/api/internal/*` is refused,** by the access service and by Caddy. Workers reach it on loopback only.
- **Every sidecar binds `127.0.0.1`.** Only Caddy listens on the container's network.
- **CORS.** The allowed origins come from `SURFSENSE_LOCAL_CORS_ORIGINS`, `*` on the desktop, whose renderer loads from `file://`. The image sets it empty: everything is same-origin.
- **Streaming.** Caddy flushes `text/event-stream` immediately, so chat and live updates stream unchanged. It sets no body limit; uploads stay capped by the API at 500 MB.
- **Behind the user's own proxy**, point it at port 80, leave `SURFSENSE_DOMAIN` empty, and keep the password, or turn sign-in off with `SURFSENSE_AUTH=none` when the proxy signs people in.

## The frontend without Electron

The image's build sets `VITE_API_BASE=/api`, which [`lib/api.ts`](../../surfsense_local/frontend/src/lib/api.ts) reads when there is no `window.surfsense?.apiUrl`. The app has no client-side router, so Caddy serves `index.html` at `/`. What differs is gated by why ([ADR 0075](../adr/0075-what-differs-in-docker-is-gated-by-one-build-flag-or-the-bridge.md)): the Electron bridge for what only Electron can do, `IN_CONTAINER` ([`in-container.ts`](../../surfsense_local/frontend/src/app/in-container.ts)) for what the Docker build does differently, and `in_container()` in the API.

| Desktop | In Docker |
|---|---|
| Open, Show in folder | Download in the row's menu, through `GET .../documents/{id}/original`; a click previews a PDF and does nothing on other files |
| electron-updater | hidden; updating is pulling a newer tag |
| Keychain secret ([ADR 0018](../adr/0018-keychain-envelope-encryption.md)) | `SURFSENSE_LOCAL_SECRET`, else `/data/secret` |
| Word and web-page previews | Word and decks through LibreOffice when Office support is on; otherwise none, refused at once |
| Claude plan, through the user's own Claude Code | the same, with Claude Code installed in the container (below) |
| About's version | the image's, from `surfsense_local/VERSION` at build time |
| Session log, the rest of About's details, crash toast | hidden |
| Usage statistics ([ADR 0070](../adr/0070-opt-in-id-less-update-checks-and-usage-statistics.md)) | none: the privacy step is hidden, and the API neither counts activity nor serves `/usage-statistics` |
| Dictation | the same over HTTPS or on the host itself; elsewhere the browser offers no microphone, and the mic says it needs HTTPS |
| The right panel's toggle | on the Studio heading's line, or the chat header's while the panel is hidden, where the desktop has it in the title bar |
| Settings › Access, the setup and sign-in screens | Docker only ([Docker access](docker-access.md)) |
| Theme, locale, external links | the browser fallbacks |

**Claude plans.** SurfSense ships no Claude Code, in the image as on the desktop. The user installs it in the container and signs in there ([Claude plan](claude-plan.md)). Anthropic's installer puts `claude` in `~/.local/bin` and the sign-in in `~/.claude`; with `HOME=/data/home` both survive an image update. In the Docker build the dialog shows, for each state, the `docker compose exec surfsense …` command with a copy button, and hides Open install guide, which installs on a desktop. Claude Code signs in by a code pasted back into the terminal, so the browser can be on any machine.

## Sign-ins

A sign-in ends where the provider sends the browser back, and in Docker that browser may be on the host or on another device. The rule for every OAuth sign-in: **the callback lands on the address the browser is already on.** The API reads that address from the request's `Host`, which Caddy and the access service have vetted, only when `in_container()`; on the desktop a page rebinding a name to the loopback API chooses its own `Host`, so it is never read ([`browser_origin.py`](../../surfsense_local/backend/modules/plugins/remote/sign_in/oauth/browser_origin.py)). A loopback address uses the port Compose publishes, given to the API as `SURFSENSE_LOCAL_PUBLIC_PORT`.

**Plugins** sign in to `<origin>/plugins/oauth/callback` ([plugins](plugins.md)), as:

| Browser on | Signs in as |
|---|---|
| the host (`localhost`) | SurfSense's hosted client document, `plugins.surfsense.com/oauth/client.json`, whose callback page forwards to `127.0.0.1:<the published port>` |
| a public domain (`SURFSENSE_DOMAIN`) | the instance's own client document, `<origin>/plugins/oauth/client.json`, whose one redirect is `<origin>/plugins/oauth/callback` |
| a LAN name | dynamic registration with `<origin>/plugins/oauth/callback`, which needs no document the provider can fetch |
| any, where the provider takes only registered apps | the user's own app, registered with the callback Settings shows ([`own_app.py`](../../surfsense_local/backend/modules/plugins/remote/sign_in/oauth/own_app.py)) |

The hosted page at `plugins.surfsense.com/oauth/callback` stays loopback-only: forwarding to an origin named in `state` would let anyone start a sign-in as SurfSense's client with their own PKCE verifier and collect the code.

**ChatGPT** signs in as OpenAI's client, which documents only a loopback redirect ([ChatGPT subscription](chatgpt-subscription.md)). The redirect is `http://127.0.0.1:<the published port>/callback`, which Caddy routes to the API's listener on its fixed port, one sign-in at a time. On the host that lands. On another device it reaches nothing, so the dialog asks for the address the failed tab ended on, and `POST /llm/connections/chatgpt/sign-in/{flow_id}/callback` hands its query to the waiting flow; the route answers only in the container. An SSH tunnel (`ssh -L 4929:localhost:4929 <server>`) makes any remote browser a loopback one, where every sign-in is automatic.

## Data and license

- `/data` holds what `~/.surfsense` holds: `surfsense.db`, `huey.db`, `secret`, `access.json`, `models/`, `embeddings/`, `images/`, `audio/`, `agent/`, `data/workspaces/`, `plugins/`, `plugin-registry/`, `imports/`, `backups/`, `runtime/office/`, and `home/`. Backing up is copying the volume.
- Migrations run when the API starts, after a backup to `backups/` ([ADR 0005](../adr/0005-hand-written-migrations.md)); workers never migrate.
- The license is entered in the app and verified offline with the keys built into the image. It has no machine binding ([ADR 0019](../adr/0019-offline-licenses.md)), so the same license works on a desktop and a server.
- The Office pack downloads into `runtime/office/` on first use, as on the desktop; the image carries the system libraries its LibreOffice links against ([Office pack](office-pack.md)).
- The container runs as a non-root `surfsense` user, uid 1000, which owns `/data`.

## The image

[`docker/surfsense/Dockerfile`](../../docker/surfsense/Dockerfile), context the repository root, on Ubuntu 24.04: the upstream llama.cpp and sd.cpp Linux builds need a recent glibc.

| Stage | Produces |
|---|---|
| `frontend` | `pnpm build` with the image's `VITE_*` settings |
| `opencode` | opencode with ripgrep, staged by `runtimes/` |
| `toolchain`, `llamacpp`, `sdcpp`, `audiocpp` | the local model runtimes, CPU builds: llama.cpp from upstream, sd.cpp compiled from the desktop's recipe without Vulkan, audio.cpp with eSpeak as the desktop builds it |
| `backend` | `uv sync` into the backend's `.venv`; torch from the CPU index |
| `models` | bge-small, the Docling parser pack, Silero VAD and the Kokoro voice, by the backend's fetch scripts |
| `backend-tests` | the backend's `pytest.mark.image` tests on the image's Ubuntu, Python and models, as uid 1000 under tini; never shipped |
| `app` | the above but the SPA: `sidecars/`, `headless/`, Node 24, Caddy, tini, and the system libraries the runtimes and LibreOffice need; what the dev stack runs |
| `runtime` | `app` with the SPA; the image |
| `frontend-dev` | Node and pnpm as uid 1000, for the dev stack's Vite; never shipped |

- `linux/amd64` only; every staging script knows `linux-x64` only.
- Several GB: torch and Docling, plus about 1 GB of bundled models. Generation weights download at run time into `/data`, as on the desktop.
- `HEALTHCHECK` calls `/api/health` through Caddy, with a start period long enough for the first migration.

## Compose

[`docker/surfsense/docker-compose.yml`](../../docker/surfsense/docker-compose.yml) runs one service, `surfsense`, on the volume `surfsense_data`, and reads `.env` beside it ([`.env.example`](../../docker/surfsense/.env.example)):

| Setting | Does |
|---|---|
| `SURFSENSE_VERSION`, `SURFSENSE_VARIANT`, `SURFSENSE_IMAGE` | which image: a tag such as `2.4.0` or `latest`; the variant is empty for CPU |
| `SURFSENSE_PORT`, `SURFSENSE_HTTPS_PORT` | the published ports, 4929 and 4943; the first is also `SURFSENSE_LOCAL_PUBLIC_PORT`, which sign-ins send the browser back to |
| `SURFSENSE_BIND` | where they publish: `0.0.0.0`, every network, or `127.0.0.1`, this machine |
| `SURFSENSE_PASSWORD`, `SURFSENSE_AUTH`, `SURFSENSE_ALLOWED_HOSTS` | the password, sign-in on or off, the names answered ([Docker access](docker-access.md)) |
| `SURFSENSE_TLS`, `SURFSENSE_DOMAIN` | HTTPS on a LAN, or for a public domain |
| `SURFSENSE_SECRET` | the secret, kept outside the volume when set |

`stop_grace_period: 30s` covers the supervisor's stop, which sends SIGKILL to a child 5 s after SIGTERM; Docker's 10 s is too tight with ten children.

## Developing the image

[`docker/surfsense/dev/compose.yml`](../../docker/surfsense/dev/compose.yml) runs the `app` stage with the checkout mounted over its source:

```bash
docker compose -f docker/surfsense/dev/compose.yml up --build --watch
```

| Changed | Takes effect |
|---|---|
| `frontend/` | at once: a `frontend` service runs Vite with the image build's `VITE_*` settings, and `dev/spa.caddy` proxies every page and the HMR socket to it in place of `frontend/dist` |
| `backend/`, `sidecars/`, `headless/`, `caddy/` | `--watch` restarts the app container, which boots as the image does |
| a dependency, a runtime's pin, a bundled model, the Dockerfile | `up --build --renew-anon-volumes`: the venv and models are the image's, on anonymous volumes Compose otherwise keeps across recreates |

- **Beside a real install.** Project `surfsense-dev`, its own data volume, ports 4930 and 4944, one above the install's, and its own `.env` in its folder.
- **Open to the machine's networks, as the install is,** so a phone tests it; `SURFSENSE_BIND=127.0.0.1` keeps it local.
- **Its tab says SurfSense Dev and wears the DEV icon** ([`dev-tab-identity.ts`](../../surfsense_local/frontend/vite-plugins/dev-tab-identity.ts)).
- **Open the two on different host names**, such as `127.0.0.1:4930` beside `localhost:4929`: browsers keep cookies per host, not per port, so on one name their session cookies overwrite each other.
- **Not the image.** The SPA is Vite's and the source is the checkout's; image changes go through `docker-tests.yml`.

## CI

- **[`docker-tests.yml`](../../.github/workflows/docker-tests.yml)** builds the image without pushing, then runs [`image.test.ts`](../../surfsense_local/headless/image.test.ts) against it, the `headless/` tests, the frontend's tests tagged `docker` in Vitest's `docker` project with the image's `VITE_*` settings and no Electron bridge, and the backend's `pytest.mark.image` tests in the `backend-tests` stage. A pull request into `dev` builds it only when it touches what can break the image: `docker/surfsense/**`, `headless/`, `sidecars/`, `runtimes/`, the bundled models' downloads, the dependency files, the frontend's build config, `VERSION` and `backend/plugins/bundles/core/**`; every `dev` push and manual run builds it. A `changes` job and a gate keep it a required check.
- **The image tests** start the CPU image and check, through Caddy: health; the app and its script served as JavaScript; that a fresh instance asks to be set up before it opens its API; `/api/internal` refused; LibreOffice's system libraries present; a clean stop; the secret kept by a new container on the same `/data`. A container with `SURFSENSE_PASSWORD` and one allowed host checks sign-in, sign-out, another host refused, a forged `X-Forwarded-Host` ignored, a sign-in callback reaching the API without a session, and a change from the app refused. One with `SURFSENSE_TLS=internal` checks HTTPS, a `Secure` cookie and the redirect from plain HTTP.
- **The build cache is on GHCR,** `:buildcache` and `:buildcache-backend-tests`, outside the repository's Actions cache. Every run reads it; `dev` pushes and release tags write it, and pull requests never do.
- The shared core's tests stay in Desktop Tests, whose `electron` filter includes `sidecars/`, `runtimes/` and `headless/`.

## Releases

The image releases with the desktop app: one version, `surfsense_local/VERSION`, one tag ([`RELEASE.md`](../../surfsense_local/RELEASE.md)).

| When | The desktop | The image ([`release-docker.yml`](../../.github/workflows/release-docker.yml)) |
|---|---|---|
| `vX.Y.Z` tag pushed | `release-local.yml` builds a draft release | builds, tests and pushes `X.Y.Z` |
| draft published by hand | GitHub's Latest moves; the in-app updater offers it | `latest` and `X.Y` move to the `X.Y.Z` digest, with no rebuild |
| `dev` push | `desktop-tests.yml` | `docker-tests.yml` builds and tests; nothing is pushed |
| `workflow_dispatch` | a dry run | a dry run, pushing nothing |

- **`latest` moves on publish, not on the tag,** so it gets the same gate as the desktop's updater: self-hosters run Watchtower or a scheduled `docker compose pull`. A pre-release or a version with a suffix never moves it.
- **A person publishes,** since GitHub starts no workflow from an event `GITHUB_TOKEN` caused.
- **The two release independently;** `RELEASE.md` checks `latest` against the new digest after publishing.
- **The names stay apart:** the legacy images keep `surfsense-backend`, `surfsense-web` and `surfsense-sandbox` on `legacy-v*` tags. A legacy self-hoster moves their data with the markdown export and import ([ADR 0022](../adr/0022-markdown-only-cloud-import.md)).

## Known gaps

- No installer: `docker/scripts/install.sh` and `install.ps1`, at the legacy installer's paths ([legacy split](../proposals/legacy-split/README.md#the-install-urls-pass-to-the-new-stack)), are not written, and the root README does not point self-hosters at the image yet.
- CPU only, and `linux/amd64` only; the CUDA variant and arm64 are the [GPU proposal](../proposals/docker-gpu.md).
- A plugin whose provider takes only SurfSense's hosted client document cannot finish a sign-in from another device on a LAN name: the hosted page forwards to loopback only, and a paste-back through it is not built. The user's own app works.
- Not verified against the real services: whether OpenAI accepts a non-loopback HTTPS redirect for ChatGPT, which would replace the paste-back; whether Notion's dynamic registration accepts a LAN HTTPS redirect; the hosted page's forward end to end, which no test exercises ([plugins](plugins.md#known-gaps)).
- No accounts or several users, no sandbox for Studio's model-written code beyond the container, and no Word or web-page previews without LibreOffice.
