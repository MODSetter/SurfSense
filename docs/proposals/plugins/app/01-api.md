# App — API

> Owns: `surfsense_local/backend/modules/plugins/router.py`, `schemas.py`.
> Routes the screen in [`02-screen.md`](02-screen.md) calls. Runtime: [`../runtime/01-process.md`](../runtime/01-process.md). Install: [`../catalog/02-install-and-publish.md`](../catalog/02-install-and-publish.md).

## Goal

The screen can list plugins, install one, set a secret, and start a run, using the modules the other streams built.

## Work

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/plugins` | The bundled catalog, or the refreshed one when `plugin_catalog` has been fetched. Each item includes `installed` version or null, `license` and whether it is unlocked, `hosts`, `yanked`. |
| `POST` | `/plugins/catalog/refresh` | Runs the refresh. Egress off → 403 with the destination name, same shape as the other egress denials. |
| `POST` | `/plugins/{id}/install` | The install function. 403 for egress, 402 for `license_required`, 409 for a bad hash or manifest. |
| `DELETE` | `/plugins/{id}` | Uninstall. |
| `PUT` | `/plugins/{id}/secrets/{name}` | Body `{ "value": str }`. Encrypts via `shared/secrets.py` under `plugin:<id>:<name>`. `name` must be in the manifest. Never returns the value. |
| `GET` | `/plugins/{id}/secrets` | Names and a boolean `set`. Never values. |
| `POST` | `/workspaces/{id}/plugins/{plugin}/entries/{entry}/runs` | Body is the inputs object. 422 when a name or kind does not match the entry. 422 when a declared secret is unset, listing the names. 402 when locked. 403 `egress_disabled` naming the first host in `hosts` that has not been allowed, the same shape as the other egress denials. Inserts `plugin_runs` and enqueues `run_plugin`. |
| `GET` | `/workspaces/{id}/plugin-runs/{run}` | Status, error, log tail, and `plugin_results` rows. |
| `POST` | `/workspaces/{id}/plugin-runs/{run}/cancel` | Sets the cancel flag the task watches. |

Emit `plugin.run.updated` on the existing events broker when a run status changes, carrying the run id, so the screen can invalidate.

## Acceptance

- List returns the example plugin from a fixture catalog with `installed: null`.
- Install, then list shows the version.
- Run with a missing required input returns 422 and does not insert a run.
- Run of a `paid` plugin with no license returns 402. With a trial license, it runs.
- Run of a plugin whose declared host has not been allowed returns 403 naming that host, and does not insert a run.
- A successful run of `plugins/example` returns a run id; polling the run reaches `succeeded`; a note exists in the workspace.
- `GET` of a secret returns `set: true` after `PUT` and does not contain the value.

## Needs from

Install, the runner task, license, egress, events. The route functions can be written and the 422 tests can land before the runner does, with the enqueue mocked. The success test waits for the runtime stream.
