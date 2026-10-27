---
status: in-progress
tracking: https://github.com/MODSetter/SurfSense/issues/2100
code:
  - docker/surfsense/
  - docker/scripts/
  - surfsense_local/sidecars/
  - surfsense_local/runtimes/
  - surfsense_local/headless/
  - surfsense_local/electron/src/main/index.ts
  - surfsense_local/backend/api/config.py
  - surfsense_local/backend/api/main.py
  - surfsense_local/backend/modules/plugins/lists/registry/registry_origin.py
  - surfsense_local/frontend/src/lib/api.ts
  - surfsense_local/frontend/src/features/models/remote/connections/claude/
  - surfsense_local/frontend/src/features/plugins/sign-in/
  - surfsense_local/backend/modules/plugins/remote/sign_in/oauth/
  - surfsense_local/backend/modules/llm/subscriptions/chatgpt/
  - backend/plugins/registry/oauth/callback.html
  - surfsense_local/backend/modules/llm/subscriptions/claude/status.py
  - .github/workflows/docker-tests.yml
  - .github/workflows/release-docker.yml
  - .github/workflows/desktop-tests.yml
  - .github/workflows/build-audiocpp.yml
  - .github/workflows/build-sdcpp.yml
  - .github/workflows/release-local.yml
---

# Running SurfSense in Docker

> The desktop app's stack, minus Electron, as one container. `surfsense_local` becomes one core with two entries: Electron for the desktop, a headless Node entry for the container. The headless entry runs the same supervisor as Electron, which starts the API, the workers, the model servers and opencode on loopback; Caddy is the only thing listening. It replaces the legacy self-host compose. The decisions are [ADR 0035](../../adr/0035-docker-compose-runs-the-desktop-stack.md), [ADR 0072](../../adr/0072-the-desktop-and-the-container-are-two-entries-over-one-core.md) and [ADR 0073](../../adr/0073-the-docker-gpu-image-is-one-cuda-12-8-variant-from-upstream-builds.md); GPU images are in [`gpu.md`](gpu.md).

**Status, 26 Oct 2026:** [steps](#steps) 1 to 4 are built, and 5 and 6, the CPU image and its workflow, are in review: the CORS origins setting ([#2122](https://github.com/MODSetter/SurfSense/pull/2122)), the `VITE_API_BASE` fallback ([#2134](https://github.com/MODSetter/SurfSense/pull/2134)), boot and the watchers with no Electron import ([#2215](https://github.com/MODSetter/SurfSense/pull/2215)), and one core with two entries: [`sidecars/`](../../../surfsense_local/sidecars/), [`runtimes/`](../../../surfsense_local/runtimes/) and the headless entry in [`headless/`](../../../surfsense_local/headless/), built on the patch on [#2104](https://github.com/MODSetter/SurfSense/issues/2104).

## What changes

| | Legacy self-host | With this |
|---|---|---|
| Images | `surfsense-backend`, `surfsense-web`, `surfsense-sandbox` | `surfsense`, one image |
| Services | Postgres, Redis, Zero, SearxNG, OpenSandbox, Caddy, backend, two Celery processes, frontend | one |
| Accounts | yes | no: one user, as on the desktop |
| Models | remote providers | the desktop catalog: llama.cpp, sd.cpp, audio.cpp, plus remote connections |
| Data | Postgres and an object store | one `/data` volume, the desktop's `~/.surfsense` layout |
| License | none | the desktop's offline Keygen license |
| Port | `3929` | `4929`, so both can run side by side while data moves over |
| Updates | Watchtower or a manual pull | pulling a newer tag; no in-app updater |

## The container

```text
surfsense container                         one port: 80, or 80 and 443 with a domain
├─ tini -g, PID 1
└─ node headless/main.ts
   ├─ caddy             0.0.0.0:80/443, the only listener
   │    /                →  frontend/dist
   │    /api/*           →  127.0.0.1:<api>, prefix stripped
   │    /api/internal/*  →  403
   │    /plugins/oauth/callback, /plugins/oauth/client.json, /callback  →  the API (sign-ins)
   └─ bootSidecars       sidecars/boot.ts, the same call Electron makes
      ├─ api                     127.0.0.1:<free port>
      ├─ worker ingest, worker studio, worker plugins
      ├─ llama-server            127.0.0.1:<free port>
      ├─ audiocpp_server         once audio/server.json names a model
      ├─ audiocpp transcription  once audio/transcription.json names a model
      ├─ sd-server               once an image model is chosen
      └─ opencode, its proxy     once agent/opencode.json exists
volume /data = SURFSENSE_LOCAL_DATA_DIR
```

One container, because the stack assumes one machine: SQLite and the Huey queue share a filesystem, the SSE broker is in memory, workers post to `/internal/events` on loopback ([`worker/notify.py`](../../../surfsense_local/backend/worker/notify.py)), and egress exempts only loopback. Split across containers, each of those breaks; in one, none changes.

### Networks

| Network | What is on it | Who reaches it |
|---|---|---|
| The container's loopback | the API, the workers, the model servers and opencode, each on a free port | processes in the container only |
| Compose's default bridge | the container's interface, with only Caddy listening, on `:80` and, with a domain, `:443` | the host, through the published port |
| The published port | `${SURFSENSE_BIND:-127.0.0.1}:${SURFSENSE_PORT:-4929}` → `80` | the host machine alone by default; the LAN with `SURFSENSE_BIND=0.0.0.0`, which joins with the password (step 10): until then compose publishes on `127.0.0.1` only |
| Outbound | NAT through the bridge | remote providers, model downloads and the plugin host, under the backend's egress rules |

- **No container talks to another.** The legacy services reached each other by name on the Compose network (`db`, `redis`, `backend`); here every call stays on loopback.
- **Two locks on the way in.** Docker publishes on the host's loopback unless `SURFSENSE_BIND` widens it, and Caddy refuses a non-local `Host` until a password is set ([Caddy and access](#caddy-and-access)). The `Host` header is the sender's to choose, so it stops a browser on the LAN and DNS rebinding, not a client that sends `Host: localhost` on purpose: `SURFSENSE_BIND` therefore arrives with the password, never before it.
- **No Docker socket.** The legacy OpenSandbox mounted `/var/run/docker.sock`, which is root on the host; this container needs nothing from the host but the volume and, on `-cuda`, the card ([`gpu.md`](gpu.md)).

## One core, two entries

`surfsense_local` is split by what runs where, as Actual Budget, Element and Trilium split theirs ([ADR 0072](../../adr/0072-the-desktop-and-the-container-are-two-entries-over-one-core.md)):

```text
surfsense_local/
  backend/     core: the API and the workers (Python)
  frontend/    core: the UI (React)
  sidecars/    core: boot, the sidecar specs, the supervisor, the watchers, net, the session log
  runtimes/    core: the pinned staging of llama.cpp, sd.cpp, audio.cpp and opencode
  electron/    desktop entry: the window, IPC, the keychain, the updater, previews, electron-builder
  headless/    container entry: the context from the environment, Caddy, the GPU check, signals
```

- **`sidecars/` imports only Node.** [`sidecars/`](../../../surfsense_local/sidecars/) is what was `electron/src/main/sidecars/`, with `net.ts`, `session-log/session-log.ts` and `session-log/main-warn.ts`, which boot imports, and `check-sidecars.mjs`, which runs the API and a worker through it. `session-log-ipc.ts` and `updater-log.ts` stay in `electron/`. A test fails on any `electron` import under `sidecars/`, so the boundary does not depend on review.
- **`runtimes/` is shared staging.** `fetch-llamacpp.mjs`, `llamacpp/`, `sdcpp/`, `audiocpp/`, `opencode/`, `not-staged/`, `pinned-download.mjs`, `msvc-runtime.mjs` and `windows-locks/` move out of `electron/scripts/`. Each takes a target and an output folder; with neither, it stages for the host into `electron/<runtime>/` as today, so electron-builder, the build artifacts and the packaged layout do not change.
- **`electron/` and `headless/` both call `bootSidecars`.** [`index.ts`](../../../surfsense_local/electron/src/main/index.ts) builds its context from `app.isPackaged` and `process.resourcesPath`; `headless/context-from-env.ts` builds it from the environment. A fix to sidecar handling lands in both.
- **Node 24 runs `sidecars/` and `headless/` as TypeScript**, with no build step, as the electron package's tests run today. Each folder has its own `package.json` and `node:test` suite.

## The headless entry

`headless/main.ts` does what `index.ts` does around boot, without a window:

1. **The context.** `context-from-env.ts` sets all ten `BootContext` fields: `packaged: false`, the backend and runtime folders under `/app`, `dataDir` from `SURFSENSE_LOCAL_DATA_DIR` (default `/data`), and the models folder.
2. **The secret, before boot.** `SURFSENSE_LOCAL_SECRET` from the environment, else `/data/secret`, created once with mode 0600 and never regenerated. Node settles it before any Python starts, so four processes never race to create the file that [`shared/secrets.py`](../../../surfsense_local/backend/shared/secrets.py) falls back to.
3. **The container's environment.** `HF_HUB_OFFLINE=1`, which [`python.ts`](../../../surfsense_local/sidecars/python.ts) sets only when `packaged` is true; `SURFSENSE_LOCAL_SIGNED_REGISTRY=1` (below); `SURFSENSE_LOCAL_RUNTIME=docker`, which the API reports where an answer differs in a container; and `HOME=/data/home`, created if missing, so what a user installs in the container keeps across updates ([Claude subscriptions](#claude-subscriptions)).
4. **No Electron previews, and no change for them.** Word and web-page previews render in a hidden `BrowserWindow`. With no desktop app polling for them, the API refuses a preview at once ([`docx_snapshots.py`](../../../surfsense_local/backend/modules/agent/previews/docx_snapshots.py)), and a Word file's or deck's pages still come from LibreOffice when Office support is on.
5. **Boot and health.** `bootSidecars`, then `/health` within 60 s, then Caddy as one more sidecar when `SURFSENSE_LOCAL_CADDYFILE` names a Caddyfile, as the image does; a checkout runs without it. Caddy gets the API's port, a free port for ChatGPT's sign-in listener, which the API is given as `SURFSENSE_LOCAL_CHATGPT_CALLBACK_PORT`, and the SPA's folder ([`caddy.ts`](../../../surfsense_local/headless/caddy.ts)), and its exit ends the process non-zero, as the API's does. It writes `/data/api-url` as `announceApiUrl` does, so `surfsense-plugins invoke` works inside the container.
6. **Signals and exit.** SIGTERM and SIGINT stop the watchers, then every child's process group. The API exiting stops the container with a non-zero code, so Compose's `restart:` applies; any other sidecar is restarted by the supervisor, as on the desktop.

### The backend's packaged switch

A venv backend reads `sys.frozen` as false, and [`registry_origin.reads_repository()`](../../../surfsense_local/backend/modules/plugins/lists/registry/registry_origin.py) then trusts the repository's unsigned plugin registry and sends plugin sign-in to a loopback callback. `reads_repository()` also returns false when `SURFSENSE_LOCAL_SIGNED_REGISTRY` is set, so the image reads the signed registry from the plugin host, as a packaged desktop does. The other `sys.frozen` checks choose how a subprocess is started, and a venv is right for them.

## Files

The new stack, in `docker/surfsense/`:

| Path | Holds |
|---|---|
| `Dockerfile` | every variant; `ARG VARIANT` picks the runtimes stage |
| `Dockerfile.dockerignore` | the ignore list, which BuildKit reads beside the Dockerfile |
| `docker-compose.yml` | the service |
| `docker-compose.gpu.yml` | the GPU device reservation, layered on top |
| `.env.example` | version, variant, port, password, hosts, domain |
| `caddy/Caddyfile` | the routes; imports one access file |
| `caddy/access.caddy` | `forward_auth` to the access service, and what bypasses it (step 10) |

Its installer, later, in `docker/scripts/`: `install.sh` and `install.ps1`, at the legacy installer's paths ([legacy split](../legacy-split/README.md#the-install-urls-pass-to-the-new-stack)). It picks the CPU or CUDA image from the host's card ([`gpu.md`](gpu.md#choosing-the-variant)).

The code, in `surfsense_local/`:

| Path | Holds |
|---|---|
| `sidecars/` | moved from `electron/src/main/sidecars/`, with `net.ts` and the session log |
| `sidecars/no-electron.test.ts` | fails on an `electron` import anywhere under `sidecars/` |
| `runtimes/` | moved from `electron/scripts/`, with a target and an output folder for the image |
| `headless/main.ts` | the container's entry: the secret, boot, `/health`, Caddy, signals |
| `headless/context-from-env.ts` | the `/data` and `/app` paths, the secret and the packaged-only environment |
| `headless/caddy.ts` | Caddy as a `SidecarSpec` |
| `headless/access/` | the sign-in service Caddy asks about each request: the password, sessions, the guess limit ([ADR 0074](../../adr/0074-docker-sign-in-is-a-surfsense-page-that-caddy-enforces.md)) |
| `frontend/src/features/access/` | the sign-in screen and Settings › Access, in the Docker build only |
| `headless/gpu-check.ts` | the no-GPU refusal ([`gpu.md`](gpu.md)) |
| `electron/src/main/index.ts` | imports `../../../sidecars/`; nothing else changes |
| `backend/modules/plugins/lists/registry/registry_origin.py` | `SURFSENSE_LOCAL_SIGNED_REGISTRY` |
| `backend/api/config.py` | `SURFSENSE_LOCAL_CORS_ORIGINS` |
| `frontend/src/lib/api.ts` | the `VITE_API_BASE` fallback |

CI is `.github/workflows/docker-tests.yml`, and releases are `.github/workflows/release-docker.yml`, as the desktop's are `desktop-tests.yml` and `release-local.yml`.

- **`docker/surfsense/`, named after the image.** `docker/` holds one folder per image, as `docker/keygen/` already is, and no file of this stack sits at a path copies of the legacy [`install.sh`](https://github.com/MODSetter/SurfSense/blob/legacy/docker/scripts/install.sh) from before 0.0.41 download from `main` (`docker/docker-compose.yml`, `docker/.env.example`, `docker/proxy/Caddyfile` and five more). The folder name is fixed from the start, because the installer fetches this stack's files by their paths.
- **The installer takes the legacy one's paths.** The one-line commands the legacy docs handed out, `…/main/docker/scripts/install.sh` and `install.ps1`, install this stack once it ships.
- **`docker/surfsense/` holds only what Docker reads.** The supervisor, the checks and the settings are application code in `surfsense_local/`.
- **The build context is the repository root.** The backend depends on `../../backend/plugins/bundles/core/manifest` ([`pyproject.toml`](../../../surfsense_local/backend/pyproject.toml)) and reads the plugin SDK from `backend/plugins/bundles/core/sdk`, so `surfsense_local/` alone cannot build it. The ignore list admits only `surfsense_local/` and those two folders.

Inside the image, the repository's layout under `/app`, so every relative path the backend resolves holds unchanged:

| Path | Holds |
|---|---|
| `/app/surfsense_local/backend/` | the source and its `.venv` |
| `/app/surfsense_local/frontend/dist/` | built with `VITE_API_BASE=/api` |
| `/app/surfsense_local/sidecars/`, `headless/` | the supervisor and the entry |
| `/app/runtimes/` | the staged `opencode/`, then `llamacpp/`, `sdcpp/` and `audiocpp/` from steps 7 to 9: one GPU backend per variant |
| `/app/surfsense_local/backend/models/` | bge-small, the Docling pack and Silero VAD; Kokoro with audio.cpp |
| `/app/caddy/` | the Caddyfile and its access file |
| `/app/backend/plugins/bundles/core/` | `manifest/` and `sdk/` |
| `/data/` | the volume |

## Caddy and access

Caddy is the one door in. A published port reaches the container's interface, never its loopback, so something must listen there and forward inward, and the API cannot be that: nothing authenticates it, and `/internal/events` is protected only by its loopback bind (ADR 0035). Caddy also serves `frontend/dist`, which Electron loads from disk on the desktop, on the same origin as `/api`, and holds HTTPS and the enforcement of access: every request but the app's static files, `/api/health` and `/access/*` goes through `forward_auth` to the headless entry's access service, which decides ([ADR 0074](../../adr/0074-docker-sign-in-is-a-surfsense-page-that-caddy-enforces.md)). Both run as sidecars in the container, not as services of their own.

| State | Answered | Sign-in |
|---|---|---|
| No password (default) | the host's own requests only: a `Host` of `localhost`, `127.0.0.1` or `[::1]`, from loopback or the bridge's gateway | none, as on the desktop |
| A password, created in the app or set by `SURFSENSE_PASSWORD` | the hosts in `SURFSENSE_ALLOWED_HOSTS`, or any | SurfSense's sign-in page |
| `SURFSENSE_DOMAIN` also | that domain | the sign-in page, over HTTPS |

- **The `Host` check is the guard.** The container cannot see how Compose published its port, but it sees the address each request was sent to. Without a password, a request to the LAN address or a domain is refused, so an unauthenticated instance cannot be reached from the network by accident. The same check stops DNS rebinding against `localhost`, which Ollama (CVE-2024-28224) and Vite (CVE-2025-24010) each had to add after the fact.
- **The sign-in.** The app's static files load without a session, carry no data, and show the sign-in screen when the API answers `401`. The access service checks one password, hashed with scrypt on `/data`, and issues an `HttpOnly`, `SameSite=Lax` session cookie, Lax so a provider's redirect back to a sign-in callback carries it, signed with a key derived from the instance's secret. Over HTTPS the cookie is also `Secure`, and it lasts 30 days. The SPA, the API and the SSE streams are one origin, so the browser sends it on all of them. Five failed sign-ins from one client within a minute answer `429`; sign-in and sign-out refuse a cross-site `Origin`; changing the password ends every session.
- **Creating the password.** Settings › Access, shown only in the Docker build, creates it from the host itself, since nothing else is answered until one exists, and changes it later. `SURFSENSE_PASSWORD` sets it at start instead, for a server with no browser of its own, and replaces a forgotten one.
- **The client address backs the `Host` check.** A `Host` header is the sender's to choose, so without a password the access service also requires the client address Caddy sees to be loopback or the bridge's gateway, which a published port on `127.0.0.1` arrives from. Docker Desktop forwards every client through its gateway, so there `SURFSENSE_BIND` stays on `127.0.0.1` until a password exists.
- **HTTPS beyond `localhost`.** A public domain gets an automatic certificate; `SURFSENSE_TLS=internal` uses Caddy's own CA on a LAN. Any access from another machine takes one of them: the password would otherwise cross the network in the clear, browsers allow the microphone only in a secure context, and OAuth allows a plain-HTTP redirect only to loopback ([Sign-ins](#sign-ins)).
- **Three root paths reach the API besides `/api/*`:** the sign-in callbacks and the instance's client document ([Sign-ins](#sign-ins)), each matched exactly, behind the same `Host` check and password.
- **`/api/internal/*` is refused.** Workers reach `/internal/events` and the transcription routes on loopback and never through Caddy.
- **Every sidecar binds `127.0.0.1`.** Only Caddy listens on the container's network.
- **CORS.** The API answers `*` today, because the desktop renderer loads from `file://` ([`api/main.py`](../../../surfsense_local/backend/api/main.py)). The allowed origins come from `SURFSENSE_LOCAL_CORS_ORIGINS`, defaulting to `*` for the desktop. The image sets it empty: everything is same-origin, so no other site can read a response.
- **Streaming.** Caddy flushes `text/event-stream` responses immediately, so chat and live updates stream unchanged. It sets no body limit; uploads stay capped by the API at 500 MB.
- **Behind the user's own proxy**, leave `SURFSENSE_DOMAIN` empty, set the password, and point the proxy at port 80.

## The frontend without Electron

Every bridge call is already optional (`window.surfsense?.…`). The build for the image sets `VITE_API_BASE=/api`, and [`lib/api.ts`](../../../surfsense_local/frontend/src/lib/api.ts) reads `window.surfsense?.apiUrl ?? import.meta.env.VITE_API_BASE ?? ""`. The app has no client-side router, so Caddy serves `index.html` at `/` with no deep-link fallback.

| Desktop | In Docker |
|---|---|
| Open, Show in folder | download through `GET .../documents/{id}/original`; PDFs preview in the app ([source preview](../source-preview.md)) |
| electron-updater | hidden; updating is pulling a newer tag |
| Keychain secret ([ADR 0018](../../adr/0018-keychain-envelope-encryption.md)) | `SURFSENSE_LOCAL_SECRET`, else `/data/secret` ([the headless entry](#the-headless-entry)) |
| Word and web-page previews | Word and decks through LibreOffice when Office support is on; otherwise none, refused at once |
| Claude subscription, through the user's own Claude Code | the same, with Claude Code installed in the container ([below](#claude-subscriptions)) |
| About's version | the image's, set when its frontend is built from `surfsense_local/VERSION` |
| Session log, the rest of About's details, crash toast | hidden |
| Theme, locale, external links | the browser fallbacks that exist |

### Claude subscriptions

SurfSense ships no Claude Code ([`locate.py`](../../../surfsense_local/backend/modules/llm/subscriptions/claude/locate.py)), in the image as on the desktop. The user installs it in the container and signs in there, and SurfSense finds it as it does on a desktop.

- **Where it lives.** Anthropic's installer puts `claude` in `~/.local/bin`, which `locate.py` searches, and the sign-in in `~/.claude`. The image sets `HOME=/data/home`, and puts its `.local/bin` on `PATH`, for every process, `docker compose exec` included. Both survive an image update, and Claude Code's own updates land there too.
- **Where the user learns how.** Clicking the Claude subscription connection opens [`claude-dialog.tsx`](../../../surfsense_local/frontend/src/features/models/remote/connections/claude/claude-dialog.tsx), which reads Claude Code's state from the API and says what to do next, with **Check again**. Its steps say "on this computer" and "open a terminal", which in Docker point at the host. When the API reports `SURFSENSE_LOCAL_RUNTIME=docker`, the claude status says so, and each state shows the container's commands, each with a copy button:

  | State | In Docker |
  |---|---|
  | `not_installed` | `docker compose exec surfsense bash -c 'set -o pipefail; curl -fsSL https://claude.ai/install.sh \| bash'`, then the sign-in below, then Check again |
  | `signed_out` | `docker compose exec -it surfsense claude`, then `/login` with the Claude account |
  | `too_old` | the install command again, which updates it |

  **Open install guide** is hidden in the container: Anthropic's guide installs on the desktop.
- **No redirect.** Claude Code signs in by a code pasted back into the terminal, so the browser can be on any machine.
- **Commands by service name.** `docker compose exec surfsense` runs as the image's user, the one the API runs as, and needs no container name.

## Sign-ins

A sign-in ends where the provider sends the browser back, and in Docker that browser may be on the host or on another machine. One rule holds for every OAuth sign-in: **the callback lands on the address the user's browser is already on**, its origin, under a client the provider allows to redirect there. The frontend sends `window.location.origin` when it starts a sign-in; the API accepts only an origin Caddy allows, and builds the redirect from it, never from a guess about where the browser is. Until step 11 only the loopback origin is served, and its port is the one compose publishes, given to the API as `SURFSENSE_LOCAL_PUBLIC_PORT`.

| The browser's origin | Example |
|---|---|
| loopback, on the Docker host | `http://localhost:4929` |
| a public domain | `https://surfsense.example.com` |
| a LAN address, with HTTPS | `https://surfsense.lan` |

The redirect never goes anywhere else. In particular, the hosted page at `plugins.surfsense.com/oauth/callback` stays loopback-only: forwarding to an origin named in `state` would let anyone start a sign-in as SurfSense's client with their own PKCE verifier and collect the code, which PKCE does not stop when the attacker made the request.

### Plugins

Every plugin, SurfSense's own, Notion or a custom server, signs in to `<origin>/plugins/oauth/callback` as the first of these identities its provider accepts. The desktop is the loopback case of the same order.

| Order | Client | Works when |
|---|---|---|
| 1 | a client ID metadata document listing that callback: SurfSense's hosted `plugins.surfsense.com/oauth/client.json` for a loopback origin, whose page forwards to `127.0.0.1:<the origin's port>`; the instance's own `<origin>/plugins/oauth/client.json` for a public one | the provider supports CIMD and can fetch the document |
| 2 | dynamic registration with that callback | the provider supports DCR; it fetches nothing, so a LAN origin works |
| 3 | the user's own app, registered with that callback ([`own_app.py`](../../../surfsense_local/backend/modules/plugins/remote/sign_in/oauth/own_app.py)) | the provider takes only registered apps |
| 4 | paste-back: a `state` that asks for it makes the hosted page show the result instead of forwarding, and the sign-in dialog takes it | everything above refused |

- **Notion fits the first two.** `mcp.notion.com` advertises both `client_id_metadata_document_supported` and a `registration_endpoint`, as the MCP authorization spec asks, so a loopback or public origin signs in through CIMD and a LAN origin through DCR.
- **The packaged switch decides less.** [`sign_in_client.py`](../../../surfsense_local/backend/modules/plugins/remote/sign_in/oauth/sign_in_client.py) picks SurfSense's hosted client when packaged and its own loopback callback otherwise; it picks by origin instead.
- **Paste-back is safe from the user's own tab.** The code is useless without the PKCE verifier, which never leaves the API, and the sign-in the user pastes into is one the API started.

### ChatGPT

ChatGPT signs in as OpenAI's client ([Sign in with ChatGPT for open-source apps](https://developers.openai.com/siwc/token-sharing-open-source)), which documents only a loopback redirect, so it follows the rule as far as OpenAI allows.

- **Loopback origin.** The redirect is `http://127.0.0.1:<the origin's port>/callback`, which Caddy routes to the API; in a container the API answers `/callback` itself instead of opening [`loopback.py`](../../../surfsense_local/backend/modules/llm/subscriptions/chatgpt/loopback.py)'s listener on a port the browser cannot reach. OpenAI accepts any loopback port.
- **Remote origin.** If OpenAI's registration accepts `<origin>/callback`, the same as above. If it accepts only loopback, the dialog takes the address the failed redirect left in the address bar, and the API finishes the exchange with its verifier; a device-code flow would replace that, should OpenAI offer one for these clients.
- **An SSH tunnel** (`ssh -L 4929:localhost:4929 <server>`) makes any remote browser a loopback one, where every sign-in is automatic.

### To verify while building

- Whether OpenAI's registration accepts a non-loopback HTTPS redirect, with a throwaway registration, before ChatGPT's remote path is built.
- Whether Notion's dynamic registration accepts any HTTPS redirect, which a LAN origin depends on.
- The hosted page's forward, end to end, which no test exercises today ([plugins](../../architecture/plugins.md#known-gaps)): the Docker smoke job signs in against a stand-in provider through Caddy.

## Data and license

- `/data` holds what `~/.surfsense` holds: `surfsense.db`, `huey.db`, `secret`, `models/`, `embeddings/`, `images/`, `audio/`, `agent/`, `data/workspaces/`, `plugins/`, `plugin-registry/`, `imports/`, `backups/`, `runtime/office/`. Backing up is copying the volume.
- Migrations run when the API starts, after a backup to `backups/` ([ADR 0005](../../adr/0005-hand-written-migrations.md)); workers never migrate.
- The license is entered in the app and kept in the database, verified offline with the keys built into the image. It has no machine binding ([ADR 0019](../../adr/0019-offline-licenses.md)), so the same license works on a desktop and a server, and it gates the same things.
- The Office runtime pack downloads into `runtime/office/` on first use, as on the desktop. The CPU image does not carry the system libraries LibreOffice needs yet; they come with the runtimes in steps 7 to 9.
- The container runs as a non-root `surfsense` user, which owns `/data`, `HOME` included.

## The image

`docker/surfsense/Dockerfile`, context the repository root, on Ubuntu 24.04: the upstream llama.cpp and sd.cpp Linux builds need a recent glibc.

| Stage | Produces |
|---|---|
| `frontend` | `pnpm build` with `VITE_API_BASE=/api` |
| `backend` | `uv sync` into the backend's `.venv`; torch from the CPU index, as [`pyproject.toml`](../../../surfsense_local/backend/pyproject.toml) pins on Linux |
| `runtimes` | llama.cpp and opencode with ripgrep from upstream, sd.cpp from the desktop's recipe, and audio.cpp with eSpeak as the desktop builds it, staged by `runtimes/` with the image's target and variant ([`gpu.md`](gpu.md#where-each-runtime-comes-from)) |
| `models` | bge-small, the Docling parser pack, Silero VAD and Kokoro, the voice the installers ship, by the backend's fetch scripts |
| `runtime` | the above, `sidecars/`, `headless/`, Node 24, Caddy and tini |

- `linux/amd64` first. `linux/arm64` follows once `runtimes/` has pinned `linux-arm64` builds of each runtime; today every staging script knows `linux-x64` only.
- Several GB: torch and Docling, plus about 1 GB of bundled models. Generation weights download at run time into `/data`, as on the desktop.
- `HEALTHCHECK` calls `/health` through loopback, with a start period long enough for the first migration.

## Compose

`docker/surfsense/docker-compose.yml`:

```yaml
name: surfsense

services:
  surfsense:
    image: ${SURFSENSE_IMAGE:-ghcr.io/modsetter/surfsense}:${SURFSENSE_VERSION:-latest}${SURFSENSE_VARIANT:+-${SURFSENSE_VARIANT}}
    ports:
      - "${SURFSENSE_BIND:-127.0.0.1}:${SURFSENSE_PORT:-4929}:80"
    volumes:
      - surfsense_data:/data
    environment:
      SURFSENSE_LOCAL_PUBLIC_PORT: ${SURFSENSE_PORT:-4929}
      SURFSENSE_LOCAL_SECRET: ${SURFSENSE_SECRET:-}
    stop_grace_period: 30s
    restart: unless-stopped

volumes:
  surfsense_data:
```

`SURFSENSE_LOCAL_PUBLIC_PORT` is the published port, which sign-ins send the browser back to. `SURFSENSE_BIND`, `SURFSENSE_PASSWORD`, `SURFSENSE_ALLOWED_HOSTS` and `SURFSENSE_DOMAIN` join with steps 10 and 11; until then the port is published on `127.0.0.1` only. `stop_grace_period` covers the supervisor's stop, which sends SIGKILL to a child 5 s after SIGTERM; Docker's default of 10 s is too tight with ten children. A GPU override file sits beside it ([`gpu.md`](gpu.md)).

## CI

### The move

Moving `sidecars/` and `runtimes/` changes the desktop's workflows in the same pull request; the packaged app does not change.

| Workflow | Change |
|---|---|
| `desktop-tests.yml` | the `electron` filter adds `surfsense_local/sidecars/**`, `runtimes/**` and `headless/**`, and the job runs their tests; job names stay, so the required checks still match |
| `build-audiocpp.yml`, `build-sdcpp.yml` | `on.paths`, the script paths and the cache keys follow `runtimes/`; the staged folder and the artifacts stay in `electron/` |
| `release-local.yml` | the staging steps call `runtimes/`; the smoke steps, which read `release/…/resources/`, do not change |
| `CODEOWNERS` | adds `sidecars/`, `runtimes/` and `headless/` |

`release-local.yml` runs only on a tag, so the pull request runs its `workflow_dispatch` dry run before it merges. The moved scripts change the sd.cpp and audio.cpp cache keys, so that run compiles both once.

### The image

Two workflows, as the desktop has: `docker-tests.yml` tests, and never pushes; `release-docker.yml` publishes. Both run [`image.test.ts`](../../../surfsense_local/headless/image.test.ts) against the image they built, off elsewhere unless `SURFSENSE_TEST_IMAGE` names one. The legacy images build from [`docker-build.yml` on the `legacy` branch](https://github.com/MODSetter/SurfSense/blob/legacy/.github/workflows/docker-build.yml), on `legacy-v*` tags.

- `docker-tests.yml` builds the image without pushing. A pull request into `dev` builds it only when it touches what can break the image itself: `docker/surfsense/**`, `headless/`, `sidecars/`, the runtimes' staging in `runtimes/`, the bundled models' downloads, the backend's and frontend's dependency files, the frontend's build config, `VERSION` and `backend/plugins/bundles/core/**`. A release pull request carries the `VERSION` bump, so it always builds the image, while a `dev` → `main` pull request of docs or `www` does not. Every `dev` push and manual run runs every job, so ordinary code that breaks the image shows on the merge into `dev`. A `changes` job and a gate keep it a required check.
- Build by digest per architecture and variant, then merge into one manifest per variant.
- The build cache is on GHCR, `:buildcache` for the image and `:buildcache-backend-tests` for the test stage, outside the repository's 10 GB Actions cache. Every run reads it; `dev` pushes in `docker-tests.yml` and release tags in `release-docker.yml` write it, and pull requests never do.
- The image tests start the CPU image, wait for `/health` through Caddy, check the app and that its script is served as JavaScript, that a non-local `Host` and `/api/internal` are refused without a password, a clean stop, and that a new container on the same `/data` keeps its secret. A second container, started with a password and one allowed host, checks the sign-in through Caddy: the API refused without a session, a wrong password refused, the right one opening the API, sign-out, another host refused, and a forged `X-Forwarded-Host` ignored. Nothing is pushed unless they pass.
- The shared core's tests stay in Desktop Tests. `docker-tests.yml` adds only what the Docker entry and the image change: the `headless/` tests, the frontend's tests tagged `docker`, in Vitest's `docker` project, with the image build's `VITE_*` settings and no Electron bridge, the compose file, and the backend's `pytest.mark.image` tests run inside the Dockerfile's `backend-tests` stage, as uid 1000 under tini, where the bundled models and system libraries are the image's.

## Releases

The image releases with the desktop app: one version, `surfsense_local/VERSION`, one tag, and one moment it goes live ([`RELEASE.md`](../../../surfsense_local/RELEASE.md)).

| When | The desktop | The image |
|---|---|---|
| `vX.Y.Z` tag pushed | `release-local.yml` builds a draft release | `release-docker.yml` builds, tests and pushes `X.Y.Z` and `X.Y.Z-<variant>` |
| draft published by hand | GitHub's Latest moves; the in-app updater offers it | a `release: published` job points `latest`, `X.Y`, `latest-<variant>` and `X.Y-<variant>` at the `X.Y.Z` digests |
| `dev` push | `desktop-tests.yml` | `docker-tests.yml` builds and tests; nothing is pushed |
| `workflow_dispatch` | a dry run | a dry run, pushing nothing |

- **`latest` moves on publish, not on the tag.** It is a retag of the digests the tag built and smoked (`docker buildx imagetools create`), with no rebuild. Until the draft is published, only someone asking for `:X.Y.Z` gets the new image; a draft that is deleted reaches nobody on `latest`.
- **`latest` is the auto-updater.** Self-hosters run Watchtower or a scheduled `docker compose pull`, as the legacy installer set up, so `latest` gets the same gate as the desktop's updater.
- **Pre-releases never move `latest`.** The publish job skips a release marked pre-release or a version with a suffix (`-rc.1`); its exact tag is pushed and nothing else.
- **A person publishes.** GitHub starts no workflow from an event that `GITHUB_TOKEN` caused, so the release is published with a maintainer's login, as `RELEASE.md` already does; publishing from a workflow would need an app token.
- **The two release independently.** A failed image build does not block the desktop release, nor the reverse; `RELEASE.md` checks `ghcr.io/modsetter/surfsense:latest` against the new version's digest after publishing.
- **The names stay apart.** The legacy images keep `surfsense-backend`, `surfsense-web` and `surfsense-sandbox` on `legacy-v*` tags, so no tag is shared.

## Leaving the legacy stack

The legacy stack is on the `legacy` branch only ([legacy split](../legacy-split/README.md)), with `legacy-v0.0.41` its final release.

1. **When the image ships:** the root README and `docker/scripts/install.*` point self-hosters at it.
2. **Then:** the legacy docs name the image as the replacement.

A legacy self-hoster moves their data with the markdown export and import ([ADR 0022](../../adr/0022-markdown-only-cloud-import.md)).

## Steps

In order; each step depends on the one before it and leaves something that runs.

**Groundwork.** The desktop app works as before after each.

1. The CORS origins setting.
2. The `VITE_API_BASE` fallback.
3. Boot and the watchers move into `sidecars/`, with no Electron import.
4. One core, two entries: `sidecars/` and `runtimes/` move out of `electron/`, with the test against Electron imports and the CI changes, then the headless entry in `headless/` and the signed-registry switch, with every doc link into the moved folders repointed. One pull request, in commits that each leave CI green, the moves as renames; the `release-local.yml` dry run passes before it merges. On a dev machine, the headless entry starts the API and the three workers, and Ctrl-C stops every child.

**The first container.**

5. The CPU image and compose on amd64, with the localhost-only access file, opencode and no local model runtimes: upload, ingest and chat through a remote connection work, and plugin and ChatGPT sign-ins finish from a browser on the host.
6. `docker-tests.yml` and `release-docker.yml`: the build and its tests, then the release jobs, with `latest` moving on publish.

**Local models, one runtime at a time.**

7. llama.cpp, with the `cpu` variant in `runtimes/`: the Linux staging is Vulkan-only today ([`gpu.md`](gpu.md#what-runtimes-gains)).
8. audio.cpp.
9. sd.cpp, with its `cpu` recipe.

**Access beyond localhost.**

10. The sign-in: the access service in `headless/access/`, `forward_auth` in Caddy, the sign-in screen and Settings › Access, `SURFSENSE_PASSWORD`, `SURFSENSE_ALLOWED_HOSTS` and `SURFSENSE_BIND` ([ADR 0074](../../adr/0074-docker-sign-in-is-a-surfsense-page-that-caddy-enforces.md)).
11. HTTPS, and sign-ins from another machine: the instance's own client document and the paste-back fallback.

**GPU images**, steps 12 to 14 in [`gpu.md`](gpu.md): `-cuda` on amd64. `linux/arm64` follows once `runtimes/` stages each runtime for it, with `-cuda13`.

Then the maintainers write `architecture/docker.md`, update the root README and both `AGENTS.md` files, and delete this proposal. `RELEASE.md` already covers the image.

## Not in scope

- Accounts, several users, several API replicas.
- A sandbox for Studio's model-written code beyond the container.
- Word and web-page previews.
- A Vulkan or ROCm image for AMD and Intel GPUs.
