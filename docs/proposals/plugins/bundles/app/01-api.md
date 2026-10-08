# App — API

> Owns: `surfsense_local/backend/modules/plugins/router.py`, `schemas.py`, the `plugin_secrets` table, and two changes outside the module: `document_metadata` on `NoteCreate`, and a list of hosts on the egress refusal.
> Routes the screen in [`02-screen.md`](02-screen.md) calls. Runtime: [`../runtime/01-process.md`](../runtime/01-process.md). Install: [`../install/01-install-update-uninstall.md`](../install/01-install-update-uninstall.md).

## Goal

The screen can list plugins, install or update one, set a secret, and start a run, using the modules the other streams built.

## Work

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/plugins` | Every plugin this app can run a version of, plus every installed one. Each item includes `available`, the version `choose_version.py` picks, or null; `installed`, the installed version, or null; `update` when `available` is newer than `installed`; `cannot_run` when the installed version must not run on this app, with its `reason` and the `offer` to move to; `access` and whether it is `locked`; and, from the installed version when there is one and otherwise from `available`, its `name`, `author`, `description`, `hosts`, the `secrets` and `actions` declarations the screen draws its forms from, and the `size` of this system's download. `needs_setup` when a declared secret has no value. |
| `POST` | `/plugins/catalog/refresh` | Runs the refresh. 403 `egress_disabled` listing the hosts not yet allowed, the same shape as the other egress denials. |
| `POST` | `/plugins/{id}/install` | Installs the version `choose_version.py` picks: a first install, an update, or a move to an older version when the installed one cannot run. 403 for egress, listing hosts. 402 for `license_required`. 404 when no version can run on this app. 409 for a bad hash or manifest. |
| `DELETE` | `/plugins/{id}` | Cancels the plugin's runs, then uninstalls. |
| `PUT` | `/plugins/{id}/secrets/{name}` | Body `{ "value": str }`. Encrypts via `shared/secrets.py` and stores it in `plugin_secrets`. `name` must be in the manifest. Never returns the value. |
| `GET` | `/plugins/{id}/secrets` | Each declared secret's name, title, description, and a boolean `set`. Never values. |
| `POST` | `/workspaces/{id}/plugins/{plugin}/actions/{action}/runs` | Body is the inputs object. 422 when an input breaks its declaration: unknown name, wrong kind, a required one missing. 422 when a declared secret has no value, listing the names. 402 when locked. 403 `egress_disabled` listing every host in `hosts` not yet allowed, so one prompt covers them all. 409 `cannot_run` with the reason and the offer when the installed version must not run on this app. Inserts `plugin_runs` as `queued` with the installed version and enqueues `run_plugin`. |
| `GET` | `/workspaces/{id}/plugin-runs` | The latest run of each action in this workspace, so the sidebar can show a run still going after the user switched away and back. |
| `GET` | `/workspaces/{id}/plugin-runs/{run}` | Status, error, and log tail. What the run produced is in the workspace already: the plugin wrote it through these same routes while it ran. |
| `POST` | `/workspaces/{id}/plugin-runs/{run}/cancel` | A `queued` run is cancelled at once. A `running` one gets the cancel flag the task watches. |

`cannot_run.reason` says which case it is, so the screen can word it: `withdrawn` with the maintainer's text, `incompatible` with the app version it stopped working on, or `newer_than_app` after a downgrade.

`plugin_secrets`: `plugin_id`, `name`, `value` (encrypted with `encrypt` from `shared/secrets.py`), with `(plugin_id, name)` unique. Hand-written migration. The runner decrypts a plugin's rows only to build its environment.

Emit `plugin.run.updated` on the existing events broker when a run's status changes, carrying the run id, so the screen can invalidate.

A plugin's note names the plugin: `NoteCreate` in `modules/documents/schemas.py` takes an optional `document_metadata` object, stored as given in the column of the same name, and reading the document returns it ([documents](../../../../architecture/documents.md#notes)). A new note with a field the app does not know is refused, so the SDK and the app cannot disagree on a name silently. The SDK's `document.add()` fills it with `{ "plugin_id", "plugin_version", "action", "run_id" }`: the id and stamped version from the plugin's packaged `manifest.json`, the action from its arguments, the run id from the environment. Nothing else sets it. It says where a note came from, for the user's benefit; loopback has no auth, so it is not an audit trail.

Several hosts in one refusal: `EgressDeniedError` carries one destination today, and the 403 built by `egress_denied` in `api/main.py` names one `destination` and `host`, which is all the prompt reads. It gains a list. The 403 adds `hosts`, every host the action still needs, and keeps `destination` and `host` as the first of them, so today's callers do not change. The prompt's side is in [`02-screen.md`](02-screen.md). This changes the egress feature, so [`egress.md`](../../../../architecture/egress.md) is updated in the same pull request.

Electron writes `http://127.0.0.1:<port>` to `api-url` in its data folder, `~/.surfsense` when packaged and `~/.surfsense-dev` in development (`electron/src/main/index.ts`), where it picks the port, and removes the file on quit. The running app does not need this — the runner passes the URL in the environment — but an author running `surfsense-plugins invoke` does, and guessing a dynamic port is not a thing to ask of a contributor. It discloses nothing: loopback already answers a port scan.

## Acceptance

- List returns the example plugin from a fixture catalog with `installed: null` and `available` set.
- List on Linux omits a fixture plugin whose only download is for Windows.
- Install, then list shows `installed` and no `update`. After a fixture catalog with a newer version this app can run, list shows `update`, and install moves to it.
- A fixture catalog with a version newer than the app does not offer that version.
- Run with a missing required input returns 422 and does not insert a run.
- Run of a `paid` plugin with no license returns 402. With a trial license, it runs.
- Run of a plugin with two declared hosts, neither allowed, returns 403 naming both, and does not insert a run.
- Run of an installed version blocked for this app returns 409 `cannot_run` with the reason and an offer, and list shows the same.
- A successful run of `plugins/example` returns a run id; polling the run reaches `succeeded`; a note exists in the workspace, and its `document_metadata` names the plugin, its version and the run.
- An egress refusal for one host still carries `destination` and `host` as before, plus `hosts` with that one host.
- `GET` of secrets returns `set: true` after `PUT` and does not contain the value.
- A run started in one workspace is listed by that workspace's `GET /workspaces/{id}/plugin-runs` and not by another's.
- Run of a plugin whose declared secret has no value returns 422 naming it.

## Needs from

Install, the runner task, license, egress, events. The route functions can be written and the 422 tests can land before the runner does, with the enqueue mocked. The success test waits for the runtime stream.
