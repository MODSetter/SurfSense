# Backend

`backend/` is the one SurfSense backend: what runs on SurfSense's own servers, as one process in one container, at `plugins.surfsense.com`. Each module is a folder; `server/` runs them together. Today its one module is SurfSense's plugins, served by the [plugin host](plugin-host.md); the [registry](plugin-registry.md) and the deferred bundles sit beside them in `plugins/`.

**Code:** [`backend/`](../../backend/)

## The tree

| Folder | Holds |
|---|---|
| [`server/`](../../backend/server/) | The process: `/health`, each module's routes mounted beside it, the image's `Dockerfile` and `entrypoint.sh`, and every setting in `.env.example` |
| [`plugins/host/`](../../backend/plugins/host/) | Serves each plugin at `/<id>/mcp`, with Stop, the usage meter and the `/license` check ([plugin host](plugin-host.md)) |
| [`plugins/mcp_server/`](../../backend/plugins/mcp_server/) | What each plugin's server builds on: who may call it, progress, results |
| [`plugins/proprietary/`](../../backend/plugins/proprietary/) | The paid plugins, their shared scraping and the license check, under the Business Source License 1.1 |
| [`plugins/registry/`](../../backend/plugins/registry/) | The third-party plugin list, served by its own static container ([registry](plugin-registry.md)) |
| [`plugins/bundles/`](../../backend/plugins/bundles/) | Deferred: the earlier, local design's SDK and tooling |

`backend/pyproject.toml` is one project for the process: every module's dependencies, and its tests.

## Imports

Python imports from two roots: `backend/` for `server`, and `backend/plugins/` for `host`, `mcp_server` and `proprietary`, so the plugins import as they did before `plugins/` moved here. pytest sets both (`pythonpath` in `pyproject.toml`), the image sets both on `PYTHONPATH`, and a local run passes the second: `cd backend && PYTHONPATH=plugins uv run python -m server`.

## The process

[`server/app.py`](../../backend/server/app.py) builds one Starlette app: `/health`, then the plugins' routes and their startup and shutdown, which [`plugins/host/app.py`](../../backend/plugins/host/app.py) hands over as `served_plugins()`. `host_app()` serves the plugins alone, with their own `/health`, for their tests. [`server/__main__.py`](../../backend/server/__main__.py) reads the settings, redacts logs before a plugin loads, and serves on `PORT`.

## The image

Coolify builds it from `backend/` with `server/Dockerfile`; the registry's from `backend/plugins/registry/`. The image leaves out `plugins/bundles/`, `plugins/registry/` and every `tests/` folder. Its working directory is `/srv/remote`, where production's usage volume is mounted at `/srv/remote/usage/`. CI builds both images on a pull request that changes what they copy in, without pushing them.

## Tests

From `backend/`, `uv run pytest` runs `server/tests/`, the host's tests and every plugin's. [`test_backend_app.py`](../../backend/server/tests/test_backend_app.py) serves the sample plugins through the backend app: `/health` answers and a plugin lists its tools at its own path.
