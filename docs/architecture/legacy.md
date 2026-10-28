# Legacy stack

The self-hosted stack from before 2.0, `surfsense_backend`, `surfsense_web`, `surfsense_mcp` and its `docker/` compose, lives only on the `legacy` branch. Nothing of it is on `dev` or `main`, and nothing on them reads from it. Its final release is `legacy-v0.0.41`; it is being phased out, so the branch simply stops being used ([ADR 0076](../adr/0076-the-legacy-stack-lives-on-its-own-branch.md)).

**Code:** the [`legacy` branch](https://github.com/MODSetter/SurfSense/tree/legacy)

## What went where

| Before the split | Now |
|---|---|
| `surfsense_backend/app/license/` behind `api.surfsense.com` | `backend/license/`, in the one [backend](backend.md) |
| `plugins/` | `backend/plugins/` |
| marketing routes inside `surfsense_web` | `www/`, its own Next.js app on Vercel at `www.surfsense.com` |
| sunset mode, `/sunset` and the sunset `/health` | removed; the backend's `/health` is plain `ok` |
| `surfsense_backend`, `surfsense_web`, `surfsense_mcp`, `docker/*` except `keygen/` | the `legacy` branch only |
| the legacy self-host compose | the [Docker image](docker.md), which shares nothing with it |
| root `VERSION` (`0.0.40`) | `VERSION` on `legacy` (`0.0.41`); `dev` has `surfsense_local/VERSION` only |

`surfsense_mcp` went with the stack because it only called the legacy backend's REST API with API keys, and those keys went with the purge.

## The branch

- **What it holds:** `surfsense_backend`, `surfsense_web`, `surfsense_mcp`, `docker/`, and the workflows `docker-build.yml`, `docker-tests.yml` and `code-quality.yml`. Everything that still ships, `surfsense_local/`, `plugins/`, `docs/` and `plans/` and their workflows, is deleted there.
- **A fix is a pull request into `legacy`,** never `dev`. Nothing else changes there.
- **On `legacy`, `/` redirects to `/login`;** the homepage it served is now `www/`.

### Its CI

Scoped by branch, not by path:

| Workflow, on `legacy` | Runs |
|---|---|
| `docker-tests.yml` | pull requests into `legacy` |
| `code-quality.yml` | pull requests into `legacy` |
| `docker-build.yml` | builds every image on pull requests and pushes to `legacy` without pushing; publishes only from a `legacy-v*` tag, and refuses one that does not match `VERSION` |

Branch protection on `legacy` requires these gates; the protection on `dev` and `main` does not list them.

## Tags and images

- **Tags are `legacy-v0.0.41`, never `v0.0.41`.** Tags are repo-wide, and a `v0.0.41` would sit beside `v2.2.3`. `release-local.yml` and `release-docker.yml` start only on `v[1-9]*`, so neither a legacy tag nor an old `v0.*` one starts a desktop or Docker release.
- **A legacy tag starts no desktop release** either way: a tag runs the workflows in the commit it points at, and `legacy` has no `release-local.yml`.
- **The images keep their names.** `ghcr.io/modsetter/surfsense-backend`, `surfsense-web` and `surfsense-sandbox` are pushed from `legacy`, and a `legacy-v*` tag moves their `latest`. The new stack is `ghcr.io/modsetter/surfsense`, so the two never share a tag.
- **Moving data across** is the markdown export and import ([ADR 0022](../adr/0022-markdown-only-cloud-import.md)); there is no database migration from the legacy stack.

## The install URLs

The legacy README's one-line commands were `…/main/docker/scripts/install.sh` and `install.ps1`. Those paths on `main` belong to the new stack's installer; no stub forwards them to `legacy`.

- `docker/scripts/install.sh`, `install.ps1`, `migrate-database.sh` and `migrate-database.ps1` live on `legacy` only, and fetch from `legacy`. The legacy README gives `curl …/legacy/docker/scripts/install.sh | bash`.
- Once written, `docker/scripts/install.sh` and `install.ps1` on `main` will install the [Docker image](docker.md#files) (see [Known gaps](#known-gaps)). The new installer is to stop on a machine with a legacy install and point at the `legacy` command, rather than start the new stack beside it: both use the compose project `surfsense` and the folder `./surfsense`.
- No new stack's file sits at a path the legacy `install.sh` from before 0.0.41 downloads from `main` (`docker/docker-compose.yml`, `docker/.env.example`, `docker/proxy/Caddyfile` and five more), which is why the image's files are in `docker/surfsense/`.

## Known gaps

- The new installer is not written, so `…/main/docker/scripts/install.sh` answers 404 ([Docker](docker.md#known-gaps)).
