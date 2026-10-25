# Backend

`backend/` is the one SurfSense backend: what runs on SurfSense's own servers, as one process in one container, at `plugins.surfsense.com` and, after the cutover, `api.surfsense.com`. Each module is a folder; `server/` runs them together. Its modules are the [license portal](license/portal.md), the mailer it sends with, and SurfSense's plugins, served by the [plugin host](plugin-host.md); the [registry](plugin-registry.md) and the deferred bundles sit beside the plugins in `plugins/`.

**Code:** [`backend/`](../../backend/)

## The tree

| Folder | Holds |
|---|---|
| [`server/`](../../backend/server/) | The process: `/health`, each module's routes mounted beside it, the image's `Dockerfile` and `entrypoint.sh`, and every setting in `.env.example` |
| [`license/`](../../backend/license/) | The license portal at `/api/v1`: download, resend, trial and Stripe's webhook ([portal](license/portal.md)), served only when `KEYGEN_API_TOKEN` is set |
| [`mailer/`](../../backend/mailer/) | Mail over SMTP; the license emails are its first user |
| [`plugins/host/`](../../backend/plugins/host/) | Serves each plugin at `/<id>/mcp`, with Stop, the usage meter and the `/license` check ([plugin host](plugin-host.md)) |
| [`plugins/mcp_server/`](../../backend/plugins/mcp_server/) | What each plugin's server builds on: who may call it, progress, results |
| [`plugins/proprietary/`](../../backend/plugins/proprietary/) | The paid plugins, their shared scraping and the license check, under the Business Source License 1.1 |
| [`plugins/registry/`](../../backend/plugins/registry/) | The third-party plugin list, served by its own static container ([registry](plugin-registry.md)) |
| [`plugins/bundles/`](../../backend/plugins/bundles/) | Deferred: the earlier, local design's SDK and tooling |

`backend/pyproject.toml` is one project for the process: every module's dependencies, and its tests.

## Imports

Python imports from two roots: `backend/` for `server`, `license` and `mailer`, and `backend/plugins/` for `host`, `mcp_server` and `proprietary`, so the plugins import as they did before `plugins/` moved here. pytest sets both (`pythonpath` in `pyproject.toml`), the image sets both on `PYTHONPATH`, and a local run passes the second: `cd backend && PYTHONPATH=plugins uv run python -m server`.

## The process

[`server/app.py`](../../backend/server/app.py) builds one FastAPI app: `/health`, the plugins' routes and their startup and shutdown, which [`plugins/host/app.py`](../../backend/plugins/host/app.py) hands over as `served_plugins()`, and the license portal's `/api/v1` router when there is one. FastAPI is Starlette underneath, so the plugins' routes mount as they are. CORS covers the whole app and lets in the site and localhost; plugins are called by the desktop app, never a web page, so it changes nothing for them. No `/docs`, `/redoc` or `/openapi.json` is served. `host_app()` serves the plugins alone, with their own `/health`, for their tests. [`server/__main__.py`](../../backend/server/__main__.py) reads the settings, redacts logs before a plugin loads, and serves on `PORT`.

## The image

Coolify builds it from `backend/` with `server/Dockerfile`; the registry's from `backend/plugins/registry/`. The image leaves out `plugins/bundles/`, `plugins/registry/` and every `tests/` folder. Its working directory is `/srv/remote`, where production's usage volume is mounted at `/srv/remote/usage/`. CI builds both images on a pull request that changes what they copy in, without pushing them.

## Tests

From `backend/`, `uv run pytest` runs `server/tests/`, the license and mailer tests, the host's tests and every plugin's. [`test_backend_app.py`](../../backend/server/tests/test_backend_app.py) serves the sample plugins through the backend app: `/health` answers, a plugin lists its tools at its own path, the license routes are served only with `KEYGEN_API_TOKEN`, CORS answers the site, and no API description is published.
