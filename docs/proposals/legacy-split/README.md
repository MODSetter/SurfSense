---
status: in-progress
code:
  - homepage/
  - docker/scripts/
  - docker/local/
  - backend/
  - surfsense_local/scripts/bump-version.sh
  - .github/workflows/
  - .pre-commit-config.yaml
  - .github/CODEOWNERS
---

# Splitting the legacy stack from what still ships

> The hosted user data was purged on 18 Oct 2026, so `surfsense_backend` and `surfsense_web` now carry three things that outlive them: the license portal, the marketing site, and the legacy self-host images. This makes `backend/` the one SurfSense backend, holding today's plugins and the license portal, moves the marketing site into `homepage/`, then moves the legacy stack to a `legacy` branch, frozen at 0.0.40, and deletes it from `dev` and `main`. The Docker image of the desktop stack ([Docker proposal](../docker/README.md)) shares nothing with it.

## What changes

| Today | After |
|---|---|
| `surfsense_backend/app/license/` behind `api.surfsense.com` | `backend/license/`, served by the one backend on `api.surfsense.com` and `plugins.surfsense.com` |
| `plugins/` | `backend/plugins/` |
| marketing routes inside `surfsense_web` | `homepage/`, its own Next.js app on Vercel |
| `surfsense_backend`, `surfsense_web`, `surfsense_mcp`, `docker/*` | the `legacy` branch only |
| `docker/scripts/install.*`, `migrate-database.*` | stubs that fetch from the `legacy` branch |
| `docker/local/` (not yet built) | `docker/local/`, unchanged |
| root `VERSION` (`0.0.40`) | `VERSION` on the `legacy` branch |

## The legacy branch

Legacy is being phased out. A branch keeps `dev` and `main` free of it from the start, so phasing it out needs no cleanup there: the branch simply stops being used.

### Cutting it

1. The backend and homepage moves land first, so the branch is cut from a tree whose legacy code no longer serves anything live.
2. `legacy` is cut at that commit ([Order](#order)).
3. On `legacy`, everything that still ships is deleted: `surfsense_local/`, `backend/`, `homepage/`, `docker/local/`, and their workflows (`release-local.yml`, `desktop-tests.yml`, `build-audiocpp.yml`, `build-sdcpp.yml`, `notarization-credentials.yml`, the `plugins-*` workflows, `release-stats.yml`).
4. On `dev`, the legacy code is deleted: `surfsense_backend/`, `surfsense_web/`, `surfsense_mcp/`, `docker/*` except `local/` and the install stubs, the root `VERSION`, `scripts/bump-version.{sh,ps1}`, `docker-build.yml` and `docker-tests.yml`. It leaves `main` with the next release merge.

### What stays on `legacy`

`surfsense_backend`, `surfsense_web`, `surfsense_mcp`, `docker/`, `docker-build.yml`, `docker-tests.yml` and `code-quality.yml`, as they are today. It stays at `0.0.40`. A bug fix, if one is ever needed, is a pull request into `legacy`; nothing else changes there.

`surfsense_mcp` goes with it because it only calls the legacy backend's REST API with an API key, and those keys went with the purge.

### Its CI

Scoped by branch, not by path:

| Workflow, on `legacy` | Change |
|---|---|
| `docker-tests.yml` | `pull_request: branches: [legacy]` |
| `docker-build.yml` | `legacy-v*` tags and `workflow_dispatch` only, no branch-push builds; refuses a tag that does not match `VERSION` |
| `code-quality.yml` | `pull_request: branches: [legacy]` |

- **Tags are `legacy-v0.0.41`, never `v0.0.41`.** Tags are repo-wide, and a `v0.0.41` would sit beside `v2.2.3`.
- **`docker-build.yml` reads the new prefix.** Today it only knows `v*` and `beta-v*`, so a `legacy-v*` tag would build nothing. Its `image_version` job runs on `refs/tags/legacy-v*`, strips `refs/tags/legacy-v` to get the version, and the `latest=` flavor matches `refs/tags/legacy-v`, so a fix moves `latest` for the installs that pull it.
- **The images keep their names.** `ghcr.io/modsetter/surfsense-backend`, `surfsense-web` and `surfsense-sandbox` are pushed from the `legacy` branch as before, and every published tag stays. The new stack publishes `ghcr.io/modsetter/surfsense`, so the two never share a tag.
- **A legacy tag starts no desktop release.** A tag runs the workflows in the commit it points at, and `legacy` has no `release-local.yml`.
- **Branch protection on `legacy`** requires the legacy gates; the protection on `dev` and `main` no longer lists them.

### The install scripts stay where they are

[`install.sh`](../../../docker/scripts/install.sh) fetches eight files by path from `main`, and the legacy docs hand out `curl …/main/docker/scripts/install.sh | bash`.

- `docker/scripts/install.sh`, `install.ps1`, `migrate-database.sh` and `migrate-database.ps1` stay as stubs that fetch their full versions from the `legacy` branch.
- The full scripts on `legacy` fetch from `legacy`, not `main`.
- They are the only legacy files left outside the branch. `docker/local/scripts/` gets the new stack's own install script later; the paths do not collide.

### What the legacy web image needs

Its `/` was the homepage. On `legacy`, `/` redirects to `/login`.

## Versions

- The desktop app and the new image share one version, today `2.2.3`, in `surfsense_local/VERSION`.
- `release-local.yml` narrows from `v*` to `v[1-9]*`, so an old `v0.*` tag never starts a desktop release.
- `docker-local.yml` releases on `v[1-9]*`.
- Legacy keeps `0.0.40` in `VERSION` on its branch, bumped by hand for a fix.

## CI outside the legacy branch

| Workflow | Starts on |
|---|---|
| `docker-local.yml` | `v[1-9]*` tags; `dev` pushes and pull requests, with a `changes` job and a gate |
| `homepage.yml` | `homepage/**` |
| `release-local.yml` | `v[1-9]*` tags |
| `desktop-tests.yml`, `plugins-*`, `code-quality.yml`, `release-stats.yml` | as today |

- **`docker-local.yml` keeps the gate pattern.** One `changes` job filters on what the Dockerfile copies in (`docker/local/**`, `surfsense_local/backend/**`, `surfsense_local/frontend/**`, `surfsense_local/electron/src/{main/sidecars,headless,session-log}/**`, `surfsense_local/electron/scripts/**`) and the other jobs skip. The gate reports either way, so it can be a required check. This narrows the [Docker proposal's](../docker/README.md#ci) `surfsense_local/**`.
- **`homepage.yml`** filters at the workflow level with `paths:`, so it is not a required check.
- **The `plugins-*` workflows keep their names and their jobs' names**, so the required checks still match; only their paths change to `backend/`. `plugins-pull-request-checks.yml` gains a job that builds the backend and registry images on pull requests touching `backend/**`, without pushing, so a wrong path in a Dockerfile fails the pull request rather than Coolify's build.
- **`.pre-commit-config.yaml`** drops the ruff, bandit and biome hooks for `surfsense_backend` and `surfsense_web`, and adds biome for `^homepage/`. `.github/CODEOWNERS` drops their entries.

### Docs that link into the legacy trees

19 files under `docs/` and `plans/` link into `surfsense_backend/` or `surfsense_web/`, and `check_docs.py` fails on a dead link. In the same change:

- Links to code that moved point at `homepage/` or `backend/license/`.
- Links to code that stays legacy-only become GitHub URLs on the `legacy` branch.
- `architecture/sunset.md` points at the `legacy` branch for its code.

## One backend

`surfsense_backend` stops, and what runs on SurfSense's servers becomes one backend: the plugins it runs today and the license portal. One folder per module, one process, one container.

```
backend/
  pyproject.toml   one project: every module's dependencies and tests
  server/          the process: its Dockerfile, its start, /health, and each module's routes mounted
  license/         the license portal: trial, resend, download, Stripe purchase and refund, the license emails
  mailer/          mail over SMTP; the license emails are its first user
  plugins/         today's plugins/, moved whole
    host/          serves each plugin at /<id>/mcp, with Stop, the usage meter and the /license check
    mcp_server/    what each plugin's server builds on: who may call it, progress, results
    proprietary/   Business Source License: the paid plugins, scraping, license_check
    registry/      the third-party list, still its own static container
    bundles/       deferred
```

- **The license is the product's, not the plugins'.** It sells and delivers the desktop app's license file, and the plugins' key check is one reader of it, so it sits beside `plugins/`.
- **Python imports from `backend/` and `backend/plugins/`.** `server`, `license` and `mailer` come from the first; `host`, `mcp_server` and `proprietary` keep their names from the second. No plugin file changes, so the move is a rename git follows.
- **`server/` assembles the process.** `host/app.py` assembles it today. Its plugin routes, and their startup and shutdown, stay in `plugins/host/`, and `server/app.py` mounts them beside `/health` and the license routes.
- **`remote/` goes.** It named SurfSense's remote plugins against `bundles/`; under `backend/plugins/` its three folders stand on their own.
- **Apache, not BSL.** `license/` and `mailer/` sit outside `plugins/proprietary/`, and the backend still runs without `proprietary/`, as a test asserts today.

### The license portal

The license code ([portal](../../architecture/license/portal.md)) has no tables, migrations, auth or Celery; Keygen and Stripe are its record ([ADR 0024](../../adr/0024-portal-without-accounts.md)). It ports file for file into `backend/license/`, and `app/mailer/` into `backend/mailer/`, on FastAPI, which becomes the backend's app, and from `app.config` to `os.environ` under the same setting names.

| Moves | From |
|---|---|
| `GET /api/v1/license/file`, `POST /api/v1/license/resend`, `POST /api/v1/license/trial` | `app/license/router.py` |
| `POST /api/v1/stripe/webhook`, license events only | `app/payments/webhook.py`, `app/license/purchase.py` |
| Keygen admin client, issuance, refunds | `keygen.py`, `issue.py`, `purchase.py`, `checkout.py`, `records.py`, `admin.py` |
| Mail | `app/mailer/`, `app/license/email/` |
| Rate limits | `rate_limit.py`, on the backend's `REDIS_URL` |
| Funnel events, cohorts | `funnel/`, `cohorts/` |
| `release.py` | written by [`bump-version.sh`](../../../surfsense_local/scripts/bump-version.sh) |
| Scripts | `issue_enterprise_license.py`, `correct_license_email.py`, `license_cohorts.py` |
| Tests | `tests/unit/license/`, the Keygen and SMTP contract tests |

### Where it runs

One container, which Coolify builds from `backend/` with `server/Dockerfile`, as it builds the plugin host today from `plugins/` with `remote/host/Dockerfile`. The registry's container builds from `backend/plugins/registry/`.

- **Served only with `KEYGEN_API_TOKEN`.** The license routes exist only when it is set, as `/admin/usage` does only with its token, so a self-hosted backend without it is unchanged.
- **`/api` is reserved**, so no plugin id can take it; `license` already is.
- **Stripe and SMTP calls run in a thread.** The same event loop streams every plugin call.
- **Dependencies.** `stripe`, `email-validator`, `disposable-email-domains` and `posthog` join `backend/pyproject.toml`.
- **Secrets.** The Keygen admin token, the Stripe secret key and the SMTP password join the backend's environment, in the container that runs headless Chromium. [ADR 0054](../../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md), which accepts one container for every plugin's secrets, and [plugin-host.md](../../architecture/plugin-host.md), which says the host holds no Keygen secret, are amended to say so.

### Two domains, one container

The Coolify service answers `https://plugins.surfsense.com,https://api.surfsense.com`. The routes keep their `/api/v1/…` paths, so the cutover is moving `api.surfsense.com` to this container:

- The homepage keeps `NEXT_PUBLIC_FASTAPI_BACKEND_URL=https://api.surfsense.com`.
- Stripe keeps its webhook URL. Until the DNS moves, `surfsense_backend` fulfils; after, only `backend/` receives the events, so a purchase is never fulfilled twice.
- The registry's paths stay on `plugins.surfsense.com` only, through the proxy rule in front ([ADR 0054](../../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md)).

What the routes need from `server/`:

- **CORS** for `https://www.surfsense.com`, exposing `Content-Disposition`, which the license download reads, on the whole app; plugins are called by the desktop app, never a page. The plugin host has none today.
- **The client IP.** The rate limits trust `CF-Connecting-IP`, then `X-Real-IP`; the Coolify proxy passes one of them.

### `/health` answers the legacy desktop

The v0.0.40 desktop asks `api.surfsense.com/health` once at startup and reads anything but `"sunset": true` as "not sunset", which loads its broken bundled frontend ([contract 4](../../contracts/04-sunset-flag.md)). The plugin host's `/health` answers plain `ok`. The backend's answers `{"status": "ok", "sunset": true, "sunset_url": "https://surfsense.com/sunset"}` instead; Coolify's health check and the Dockerfile's `HEALTHCHECK` read only the status code, and the current desktop never asks `plugins.surfsense.com` for `/health`.

### What the move changes with it

Each of these breaks unless it changes in the same pull request or at its merge:

| What | Change |
|---|---|
| Coolify's two builds | The backend from `backend/` with `server/Dockerfile`, the registry from `backend/plugins/registry/`; set when the move reaches the branch Coolify deploys from |
| [`proprietary/LICENSE`](../../../backend/plugins/proprietary/LICENSE) | Its Licensed Work, `plugins/remote/proprietary/**`, becomes `backend/plugins/proprietary/**`, approved by that folder's code owners |
| The site's `/terms` and `/plugins` | `/terms` names the same folder, and `/plugins` links to `tree/main/plugins/registry`; both take the new paths |
| Five workflows, `CODEOWNERS`, `AGENTS.md`, `plugins/README.md`, and every doc and comment naming the old paths | The new paths; `check_docs.py` fails on a dead link left behind |
| The desktop backend, which installs the bundles' manifest rules from `../../plugins/bundles/core/manifest`, and in development reads the bundle SDK and the registry from the checkout | `backend/plugins/bundles/core/manifest` in its `pyproject.toml` and `uv.lock`, and the two development paths; an image that installs the desktop backend copies that folder in |

## The homepage

`homepage/` is a Next.js app deployed on Vercel at `www.surfsense.com`.

| Moves | From `surfsense_web/` |
|---|---|
| Routes | `app/(home)/**` except `login/` and `register/`; `app/docs`; `app/api/search`; `sitemap.ts`, `robots.ts`, `not-found.tsx` |
| Desktop services | `app/api/updates`, `app/api/usage`, serving `updates.` and `usage.surfsense.com` ([updates](../../architecture/updates.md), [contract 5](../../contracts/05-desktop-telemetry.md)) |
| Content | `content/docs`, `blog/`, `changelog/`, `announcements/`, `source.config.ts`, `mdx-components.tsx` |
| Components | `homepage/`, `site/`, `pricing/`, `contact/`, `marketing/`, `seo/`, and the `ui/` primitives they import |
| Lib | `app-release.ts`, `release-assets.ts`, `free-models`, `docs-redirects.ts`, `posthog/`, `features/funnel-attribution/` |
| Assets | `public/` except `connectors/` and `infographic-styles/` |

- **Shared pieces are copied.** The public chat imports the homepage navbar, `changelog-timeline` imports homepage primitives, and the app's sidebar reads announcements. The `legacy` branch keeps its own copies.
- **`/sunset` becomes static.** The purge left nothing to export, so the export button goes; the download links and import steps stay. `SUNSET_URL` and the v0.0.40 desktop still resolve it at `surfsense.com/sunset`.
- **Paths that point at `surfsense_web`:** Vercel's root directory, the banner image in all 11 READMEs, `surfsense_local/scripts/bump-version.sh` (writes `app-release.ts`) and `surfsense_local/RELEASE.md` (changelog entries).
- **Tests.** The unit tests for downloads, checkout, sunset, docs redirects, funnel attribution and the update feed move with their code. No e2e spec covers marketing pages today.

## The Docker image

Built as the [Docker proposal](../docker/README.md#steps) sets out, steps 4 to 14 (#2104 to #2114). It reads nothing from the `legacy` branch.

## Order

The backend lands first, in its own pull request into `dev`:

1. `plugins/` moves to `backend/plugins/`, `server/` assembles the process, and everything in [What the move changes with it](#what-the-move-changes-with-it) changes with it, with the job that builds the images.
2. The license portal and the mailer into `backend/license/` and `backend/mailer/`.

Then one pull request into `dev`, in commits that each leave CI green:

3. The sunset `/health`.
4. The homepage split.
5. The legacy code deleted, the install stubs, the narrowed `release-local.yml`, the CI and hook changes, and the repointed doc links.
6. The Docker steps 4 to 14.

The `legacy` branch is cut from the second pull request's branch at commit 4, before commit 5 deletes anything, and trimmed in its own commit on `legacy`.

The backend's pull request adds `architecture/backend.md` and updates `portal.md`, `plugin-host.md`, `plugin-registry.md`, ADR 0024, ADR 0054 and the root `AGENTS.md`. After the second, `architecture/` gains `homepage.md` and `docker.md`; `sunset.md`, the purge runbook, the root README and both `AGENTS.md` files are updated; this proposal and the Docker proposal are deleted.

## Cutover

1. When the move reaches the branch Coolify deploys from, point its two services at the new paths ([Where it runs](#where-it-runs)).
2. Deploy the backend with the license settings; `api.surfsense.com` still points at `surfsense_backend`.
3. Once the sunset `/health` is deployed, add `api.surfsense.com` to the backend's Coolify domains and move its DNS.
4. Check `GET /health`, a trial request and a Stripe test-mode purchase against `api.surfsense.com`.
5. Switch off the hosted backend and the hosted MCP server at `mcp.surfsense.com`.
