# App — API

> Owns: `surfsense_local/backend/modules/plugins/router.py`, `schemas.py`, and two changes outside the module: provenance on `NoteCreate`, and a list of hosts on the egress refusal.
> Routes the screen in [`02-screen.md`](02-screen.md) calls. Runtime: [`../runtime/01-process.md`](../runtime/01-process.md). Install: [`../catalog/03-install.md`](../catalog/03-install.md).

## Goal

The screen can list plugins, install or update one, set a secret, and start a run, using the modules the other streams built.

## Work

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/plugins` | Every catalog plugin this app can install, plus every installed one. Hidden: a plugin with no download for this system, and one whose current version is yanked and not installed. Each item includes `installed` version or null, `update` (the newer version, or null), `needs_newer_app`, `access` and whether it is `locked`, `description`, `hosts`, the `secrets` and `entries` declarations the screen draws its forms from, `needs_setup` when a declared secret has no value, the `size` of this system's download, and `withdrawn` with the reason when the installed version is yanked. |
| `POST` | `/plugins/catalog/refresh` | Runs the refresh. 403 `egress_disabled` listing the hosts not yet allowed, the same shape as the other egress denials. |
| `POST` | `/plugins/{id}/install` | Installs, or updates an installed plugin to the catalog's version. 403 for egress, listing hosts. 402 for `license_required`. 404 when there is no download for this system. 409 for a bad hash or manifest, `yanked`, or `needs_newer_app`. |
| `DELETE` | `/plugins/{id}` | Cancels the plugin's runs, then uninstalls. |
| `PUT` | `/plugins/{id}/secrets/{name}` | Body `{ "value": str }`. Encrypts via `shared/secrets.py` under `plugin:<id>:<name>`. `name` must be in the manifest. Never returns the value. |
| `GET` | `/plugins/{id}/secrets` | Each declared secret's name, title, description, and a boolean `set`. Never values. |
| `POST` | `/workspaces/{id}/plugins/{plugin}/entries/{entry}/runs` | Body is the inputs object. 422 when an input breaks its declaration: unknown name, wrong kind, a required one missing. 422 when a declared secret has no value, listing the names. 402 when locked. 403 `egress_disabled` listing every host in `hosts` not yet allowed, so one prompt covers them all. 409 `yanked` with the reason, or `needs_newer_app`. Inserts `plugin_runs` as `queued` with the installed version and enqueues `run_plugin`. |
| `GET` | `/workspaces/{id}/plugin-runs/{run}` | Status, error, and log tail. What the run produced is in the workspace already: the plugin wrote it through these same routes while it ran. |
| `POST` | `/workspaces/{id}/plugin-runs/{run}/cancel` | A `queued` run is cancelled at once. A `running` one gets the cancel flag the task watches. |

Emit `plugin.run.updated` on the existing events broker when a run's status changes, carrying the run id, so the screen can invalidate.

Provenance: `NoteCreate` in `modules/documents/schemas.py` gains an optional `metadata` object, `{ "plugin_id", "plugin_version", "entry", "run_id" }`, stored in the `document_metadata` column that already exists. The SDK's `document.add()` fills it: the id and version from the plugin's own `plugin.json`, the entry from its arguments, the run id from the environment. Nothing else sets it. It says where a note came from, for the user's benefit; loopback has no auth, so it is not an audit trail.

Several hosts in one refusal: `EgressDeniedError` carries one destination today, and the 403 built by `egress_denied` in `api/main.py` names one `destination` and `host`, which is all the prompt reads. It gains a list. The 403 adds `hosts`, every host the action still needs, and keeps `destination` and `host` as the first of them, so today's callers do not change. The prompt's side is in [`02-screen.md`](02-screen.md). This changes the egress feature, so [`egress.md`](../../../architecture/egress.md) is updated in the same pull request.

Electron writes `http://127.0.0.1:<port>` to `~/.surfsense/api-url` where it picks the port (`electron/src/main/index.ts`), and removes the file on quit. The running app does not need this — the runner passes the URL in the environment — but an author running the harness does, and guessing a dynamic port is not a thing to ask of a contributor. It discloses nothing: loopback already answers a port scan.

## Acceptance

- List returns the example plugin from a fixture catalog with `installed: null`.
- List on Linux omits a fixture plugin whose only download is for Windows.
- Install, then list shows the version and `update: null`. After a newer fixture catalog, list shows `update`, and install moves to it.
- Run with a missing required input returns 422 and does not insert a run.
- Run of a `paid` plugin with no license returns 402. With a trial license, it runs.
- Run of a plugin with two declared hosts, neither allowed, returns 403 naming both, and does not insert a run.
- Run of an installed version that is yanked returns 409 with the reason.
- A successful run of `plugins/example` returns a run id; polling the run reaches `succeeded`; a note exists in the workspace, and its metadata names the plugin and the run.
- An egress refusal for one host still carries `destination` and `host` as before, plus `hosts` with that one host.
- `GET` of secrets returns `set: true` after `PUT` and does not contain the value.
- Run of a plugin whose declared secret has no value returns 422 naming it.

## Needs from

Install, the runner task, license, egress, events. The route functions can be written and the 422 tests can land before the runner does, with the enqueue mocked. The success test waits for the runtime stream.
