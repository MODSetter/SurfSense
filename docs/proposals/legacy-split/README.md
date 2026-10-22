---
status: proposed
code:
  - homepage/
  - docker/scripts/
  - docker/local/
  - plugins/remote/license/
  - plugins/remote/host/
  - surfsense_local/scripts/bump-version.sh
  - .github/workflows/
  - .pre-commit-config.yaml
  - .github/CODEOWNERS
---

# Splitting the legacy stack from what still ships

> The hosted user data was purged on 18 Oct 2026, so `surfsense_backend` and `surfsense_web` now carry three things that outlive them: the license portal, the marketing site, and the legacy self-host images. This moves the license routes into the plugin host and the marketing site into `homepage/`, then moves the legacy stack to a `legacy` branch, frozen at 0.0.40, and deletes it from `dev` and `main`. The Docker image of the desktop stack ([Docker proposal](../docker/README.md)) shares nothing with it.

## What changes

| Today | After |
|---|---|
| `surfsense_backend/app/license/` behind `api.surfsense.com` | `plugins/remote/license/`, served by the plugin host on `api.surfsense.com` and `plugins.surfsense.com` |
| marketing routes inside `surfsense_web` | `homepage/`, its own Next.js app on Vercel |
| `surfsense_backend`, `surfsense_web`, `surfsense_mcp`, `docker/*` | the `legacy` branch only |
| `docker/scripts/install.*`, `migrate-database.*` | stubs that fetch from the `legacy` branch |
| `docker/local/` (not yet built) | `docker/local/`, unchanged |
| root `VERSION` (`0.0.40`) | `VERSION` on the `legacy` branch |

## The legacy branch

Legacy is being phased out. A branch keeps `dev` and `main` free of it from the start, so phasing it out needs no cleanup there: the branch simply stops being used.

### Cutting it

1. The license and homepage moves land first, so the branch is cut from a tree whose legacy code no longer serves anything live.
2. `legacy` is cut at that commit ([Order](#order)).
3. On `legacy`, everything that still ships is deleted: `surfsense_local/`, `plugins/`, `homepage/`, `docker/local/`, and their workflows (`release-local.yml`, `desktop-tests.yml`, `build-audiocpp.yml`, `build-sdcpp.yml`, `notarization-credentials.yml`, the `plugins-*` workflows, `release-stats.yml`).
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
- **`.pre-commit-config.yaml`** drops the ruff, bandit and biome hooks for `surfsense_backend` and `surfsense_web`, and adds biome for `^homepage/`. `.github/CODEOWNERS` drops their entries.

### Docs that link into the legacy trees

19 files under `docs/` and `plans/` link into `surfsense_backend/` or `surfsense_web/`, and `check_docs.py` fails on a dead link. In the same change:

- Links to code that moved point at `homepage/` or `plugins/remote/license/`.
- Links to code that stays legacy-only become GitHub URLs on the `legacy` branch.
- `architecture/sunset.md` points at the `legacy` branch for its code.

## License routes into the plugin host

The license code ([portal](../../architecture/license/portal.md)) has no tables, migrations, auth or Celery; Keygen and Stripe are its record ([ADR 0024](../../adr/0024-portal-without-accounts.md)). It ports from FastAPI to the host's Starlette and `os.environ`.

| Moves | From |
|---|---|
| `GET /api/v1/license/file`, `POST /api/v1/license/resend`, `POST /api/v1/license/trial` | `app/license/router.py` |
| `POST /api/v1/stripe/webhook`, license events only | `app/payments/webhook.py`, `app/license/purchase.py` |
| Keygen admin client, issuance, refunds | `keygen.py`, `issue.py`, `purchase.py`, `checkout.py`, `records.py`, `admin.py` |
| Mail | `app/mailer/`, `app/license/email/` |
| Rate limits | `rate_limit.py`, on the host's `REDIS_URL` |
| Funnel events, cohorts | `funnel/`, `cohorts/` |
| `release.py` | written by [`bump-version.sh`](../../../surfsense_local/scripts/bump-version.sh) |
| Scripts | `issue_enterprise_license.py`, `correct_license_email.py`, `license_cohorts.py` |
| Tests | `tests/unit/license/`, the Keygen and SMTP contract tests |

### Where it runs

In the plugin host's container, the one Coolify builds from `plugins/` with `remote/host/Dockerfile`.

- **`plugins/remote/license/`.** The build context is `plugins/`, so a root `license/` would not reach the image. The Dockerfile's `COPY remote/ .` already ships the folder. It has no `server.py`, and `license` is on the host's reserved list ([`mounted_plugins.py`](../../../plugins/remote/host/mounted_plugins.py)), so it is never mounted as a plugin.
- **Apache, not BSL.** It sits outside `proprietary/`; a test asserts the host builds without it.
- **`app.py`** mounts its routes beside `/license`, `/cancel` and `/admin`. `api` joins the reserved list, so no plugin id can take `/api`.
- **Dependencies.** `stripe`, `email-validator`, `disposable-email-domains` and `posthog` join [`host/pyproject.toml`](../../../plugins/remote/host/pyproject.toml).
- **Secrets.** The Keygen admin token, the Stripe secret key and the SMTP password join the host's environment, in the container that runs headless Chromium. [ADR 0054](../../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md), which accepts one container for every plugin's secrets, and [plugin-host.md](../../architecture/plugin-host.md), which says the host holds no Keygen secret, are amended to say so.

### Two domains, one container

The Coolify service answers `https://plugins.surfsense.com,https://api.surfsense.com`. The routes keep their `/api/v1/…` paths, so the cutover is moving `api.surfsense.com` to this container:

- The homepage keeps `NEXT_PUBLIC_FASTAPI_BACKEND_URL=https://api.surfsense.com`.
- Stripe keeps its webhook URL. Until the DNS moves, the hosted backend fulfils; after, only the host receives the events, so a purchase is never fulfilled twice.
- The registry's paths stay on `plugins.surfsense.com` only, through the proxy rule in front ([ADR 0054](../../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md)).

What the routes need from the host:

- **CORS** for `https://www.surfsense.com`, exposing `Content-Disposition`, which the license download reads. The host has none today.
- **The client IP.** The rate limits trust `CF-Connecting-IP`, then `X-Real-IP`; the Coolify proxy passes one of them.

### `/health` answers the legacy desktop

The v0.0.40 desktop asks `api.surfsense.com/health` once at startup and reads anything but `"sunset": true` as "not sunset", which loads its broken bundled frontend ([contract 4](../../contracts/04-sunset-flag.md)). The host's `/health` answers plain `ok`. It answers `{"status": "ok", "sunset": true, "sunset_url": "https://surfsense.com/sunset"}` instead; Coolify's health check and the Dockerfile's `HEALTHCHECK` read only the status code, and the current desktop never asks the plugin host for `/health`.

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

One pull request into `dev`, in commits that each leave CI green:

1. License routes into the plugin host, with the Stripe webhook and the sunset `/health`.
2. The homepage split.
3. The legacy code deleted, the install stubs, the narrowed `release-local.yml`, the CI and hook changes, and the repointed doc links.
4. The Docker steps 4 to 14.

The `legacy` branch is cut from this pull request's branch at commit 2, before commit 3 deletes anything, and trimmed in its own commit on `legacy`.

Then `architecture/` gains `homepage.md` and `docker.md`; `portal.md`, `plugin-host.md`, `sunset.md`, ADR 0024, ADR 0054, the purge runbook, the root README and both `AGENTS.md` files are updated; this proposal and the Docker proposal are deleted.

## Cutover

1. Deploy the host with the license routes; `api.surfsense.com` still points at the backend.
2. Add `api.surfsense.com` to the host's Coolify domains and move its DNS.
3. Check `GET /health`, a trial request and a Stripe test-mode purchase against `api.surfsense.com`.
4. Switch off the hosted backend and the hosted MCP server at `mcp.surfsense.com`.
