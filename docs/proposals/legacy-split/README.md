---
status: proposed
code:
  - legacy/
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

> The hosted user data was purged on 18 Oct 2026, so `surfsense_backend` and `surfsense_web` now carry three things that outlive them: the license portal, the marketing site, and the legacy self-host images. This moves the license routes into the plugin host, the marketing site into `homepage/`, and the legacy stack into `legacy/`, frozen at 0.0.40 with its CI still green. The Docker image of the desktop stack ([Docker proposal](../docker/README.md)) is built beside it and shares nothing with it.

## What changes

| Today | After |
|---|---|
| `surfsense_backend/app/license/` behind `api.surfsense.com` | `plugins/remote/license/`, served by the plugin host on `api.surfsense.com` and `plugins.surfsense.com` |
| marketing routes inside `surfsense_web` | `homepage/`, its own Next.js app on Vercel |
| `docker/*`, `surfsense_backend`, `surfsense_web` | `legacy/docker/`, `legacy/surfsense_backend/`, `legacy/surfsense_web/` |
| `docker/local/` (not yet built) | `docker/local/`, unchanged |
| `docker-build.yml`, `docker-tests.yml` | `legacy-docker-build.yml`, `legacy-tests.yml` |
| root `VERSION` (`0.0.40`) | `legacy/VERSION` |

## Versions

- Legacy ends at `0.0.40` and takes bug fixes only (`0.0.41`, …). Its version lives in `legacy/VERSION`, bumped by hand.
- Legacy releases are tagged `legacy-v0.0.41`, never `v0.0.41`. `legacy-docker-build.yml` runs only on `legacy-v*` tags and `workflow_dispatch`, and refuses a tag that does not match `legacy/VERSION`, as `release-local.yml` does for `surfsense_local/VERSION`.
- `release-local.yml` narrows from `v*` to `v[1-9]*`, so neither a legacy tag nor an old `v0.*` tag starts a desktop release.
- The desktop app and the new image share one version, today `2.2.3`. `docker-local.yml` releases on `v[1-9]*`.

## The legacy stack

### What moves

`docker/*` except `local/`, plus `surfsense_backend/` and `surfsense_web/`, move under `legacy/` with `git mv`. Nothing in them changes beyond the paths that point at each other.

### The install scripts stay put

[`install.sh`](../../../docker/scripts/install.sh) fetches eight files by path from `main`, and the legacy docs hand out `curl …/main/docker/scripts/install.sh | bash`. Moving them would 404 every re-install and update.

- `docker/scripts/install.sh`, `install.ps1`, `migrate-database.sh` and `migrate-database.ps1` stay, as stubs that fetch their full versions from `legacy/docker/scripts/`.
- The full scripts in `legacy/` fetch from `legacy/docker/…`.
- `docker/local/scripts/` gets the new stack's own install script later; the paths do not collide.

### Its CI

Workflow files cannot leave `.github/workflows/`, so they are repointed:

| File | Change |
|---|---|
| `legacy-docker-build.yml` | `legacy-v*` tags and `workflow_dispatch` only, no branch-push builds; version from `legacy/VERSION`; contexts under `legacy/` |
| `legacy-tests.yml` | `pull_request` `paths:` of `legacy/**` and itself, so no other change starts it |
| `release-local.yml` | trigger narrowed to `v[1-9]*` |
| `.pre-commit-config.yaml` | ruff, bandit and biome `files:` to `^legacy/surfsense_backend/` and `^legacy/surfsense_web/` |
| `.github/CODEOWNERS` | the moved paths |
| `scripts/bump-version.{sh,ps1}` | move to `legacy/scripts/`; bump `legacy/VERSION` and the legacy `package.json` and `pyproject.toml`, by hand |

The legacy web image needs its own `/` once the homepage leaves it: a redirect to `/login`.

### Scoping

Each workflow starts only for its own files, and lists its own `.github/workflows/<name>.yml` among them:

| Workflow | Starts on |
|---|---|
| `legacy-tests.yml` | `legacy/**` |
| `legacy-docker-build.yml` | `legacy-v*` tags and manual runs |
| `docker-local.yml` | `v[1-9]*` tags; on `dev`, `docker/local/**`, `surfsense_local/backend/**`, `surfsense_local/frontend/**`, `surfsense_local/electron/src/{main/sidecars,headless,session-log}/**`, `surfsense_local/electron/scripts/**` |
| `homepage.yml` | `homepage/**` |
| `release-local.yml` | `v[1-9]*` tags |

A workflow-level `paths:` means the workflow never starts, so its gate job never reports. If a gate is a required check in branch protection, the requirement becomes per-workflow, or a PR that does not touch those files waits forever.

The `dev` filter for `docker-local.yml` is narrower than the [Docker proposal's](../docker/README.md#ci) `surfsense_local/**`; that proposal takes the same list.

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
- Stripe keeps its webhook URL. The backend's registration in `purchase.py` is removed in the same change, so a purchase is never fulfilled twice.
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

- **Shared pieces are copied, not shared.** The public chat imports the homepage navbar, `changelog-timeline` imports homepage primitives, and the app's sidebar reads announcements. Legacy keeps frozen copies; there is no shared package between a live tree and a frozen one.
- **`/sunset` becomes static.** The purge left nothing to export, so the export button goes; the download links and import steps stay. `SUNSET_URL` and the v0.0.40 desktop still resolve it at `surfsense.com/sunset`.
- **Paths that point at `surfsense_web`:** Vercel's root directory, the banner image in all 11 READMEs, `surfsense_local/scripts/bump-version.sh` (writes `app-release.ts`) and `surfsense_local/RELEASE.md` (changelog entries).
- **CI.** `homepage.yml` runs biome and `pnpm test:unit`, with a biome hook scoped to `^homepage/`. The unit tests for downloads, checkout, sunset, docs redirects, funnel attribution and the update feed move with their code. No e2e spec covers marketing pages today.

## The Docker image

Built as the [Docker proposal](../docker/README.md#steps) sets out, steps 4 to 14 (#2104 to #2114). It reads nothing from `legacy/` and `legacy/` reads nothing from `docker/local/`.

## Order

One pull request, in commits that each leave CI green:

1. License routes into the plugin host, with the Stripe webhook and the sunset `/health`.
2. The homepage split.
3. The `legacy/` move, `legacy/VERSION`, the install-script stubs, the repointed and scoped CI, and the narrowed `release-local.yml` trigger.
4. The Docker steps 4 to 14.

Then `architecture/` gains `homepage.md` and `docker.md`; `portal.md`, `plugin-host.md`, `sunset.md`, ADR 0024, ADR 0054, the purge runbook, the root README and both `AGENTS.md` files are updated; this proposal and the Docker proposal are deleted.

## Cutover

1. Deploy the host with the license routes; `api.surfsense.com` still points at the backend.
2. Add `api.surfsense.com` to the host's Coolify domains and move its DNS.
3. Check `GET /health`, a trial request and a Stripe test-mode purchase against `api.surfsense.com`.
4. Switch the hosted backend off.
