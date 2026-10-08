# Runtime — process

> Owns: `surfsense_local/backend/modules/plugins/runner/`, `modules/plugins/tasks.py`, the `plugin_runs` table, the `plugins` queue and its worker, and one change outside the module: deleting a workspace stops its runs first.
> Contract: [`../01-protocol.md`](../01-protocol.md).

## Goal

The worker starts a plugin process for one run, hands it its context, and records how it ended. There is nothing to import afterwards: the plugin wrote through the app's API while it ran. A run never outlives the app.

## Work

- Hand-written migration for `plugin_runs`: `id`, `workspace_id`, `plugin_id`, `version`, `action`, `inputs` JSON, `status` (`queued` `running` `succeeded` `failed` `cancelled`), `error`, `log_tail`, `created_at`, `started_at`, `finished_at`. `version` is the installed version the run uses, the one its release stamped, so install knows which directory is still open. `error` is the reason from the protocol's outcome table.
- `import_models()` and `import_tasks()` gain this module the same way the other modules do. A test in the existing registration test fails if they are missing.
- A `plugins` queue in `shared/queue.py`, drained by its own worker: one queue per consumer, as that file already does, so a plugin run never takes a slot from ingest or Studio. Plugin runs mostly wait on the network, as Studio jobs wait on a model, so the consumer runs four threads beside `STUDIO_WORKERS`; a fifth run waits as `queued`. That is the only limit on concurrent runs. Electron starts it as `worker-plugins` beside the other two (`WorkerQueue` in `electron/src/main/sidecars/python.ts`).
- Huey task `run_plugin(run_id)`. The API enqueues it. It sets `running`, then spawns the interpreter from `plugin_python()` ([`../python/01-interpreter.md`](../python/01-interpreter.md) supplies the packaged path; until then `plugin_python()` returns the interpreter running the worker, which is a real one in development and in tests).
- Arguments, as the protocol specifies: `<plugin-dir> <action> --inputs <file> --data <dir>`. The task writes the inputs file in a directory of its own that it deletes when the run ends. Working directory is the plugin directory. `PYTHONPATH` is the SDK directory shipped next to the interpreter; the SDK adds `<plugin-dir>` and its `site-packages` itself.
- The environment is built from scratch, never copied from the worker's, exactly as the protocol lists it: the `SURFSENSE_PLUGIN_*` context, one `SURFSENSE_PLUGIN_SECRET_<NAME>` per declared secret, decrypted only here, the operating-system allowlist, and the Python variables. A test spawns a plugin that prints its environment and fails on `SURFSENSE_LOCAL_SECRET` or any other `SURFSENSE_LOCAL_` name. The API has already refused the run when a declared secret has no value, or when a host in `hosts` has not been allowed.
- The API URL is the worker's own: Electron passes `SURFSENSE_LOCAL_HOST` and `SURFSENSE_LOCAL_PORT` to this process already (`electron/src/main/sidecars/python.ts`), so build it from those rather than inventing a second source of truth.
- Capture stdout and stderr into a ring of 16 KiB on `log_tail`.
- Exit 0 sets `succeeded`. Any other exit sets `failed` with `error` of `exit <code>`.
- Timeout: the task stops the plugin once it has run for its action's `timeout_seconds` (1800 when the action sets none) and sets `failed` with `timeout`.
- Stopping, for cancel and for timeout: `SIGTERM` to the plugin and every process it started, `SIGKILL` five seconds later. Walk the tree with `psutil`, a direct dependency. Cancel sets the run `cancelled`; the task looks every second, stops the plugin, and records when it ended. Cancelling a `queued` run revokes its task with `revoke_pending` and sets `cancelled` at once. Whatever the plugin already committed through the API stays, because it was committed when the call returned.
- Deleting a workspace cancels its `queued` and `running` plugin runs and waits for them to stop, as uninstall does, and only then deletes it (`delete_workspace` in `modules/workspaces/router.py`). It waits at most ten seconds: a run still going after that has no worker, and its plugin stopped with it. `plugin_runs.workspace_id` cascades on delete, so no run record outlives its workspace. Without this, the plugin's next write is refused because the workspace is gone, and the run fails with a reason that has nothing to do with the plugin.
- Never detach a plugin: no new session, no new process group, no `CREATE_NEW_PROCESS_GROUP`. The supervisor stops each worker with its whole process group on macOS and Linux, and with `taskkill /t` on Windows (`electron/src/main/sidecars/supervisor.ts`), so a plugin and everything it started stop when the app quits.
- When the `plugins` worker starts, before it takes a job, every `running` row and every `queued` row created before that moment becomes `failed` with `interrupted`, and their pending tasks are revoked. A `running` row needs no time check: no job of the new worker has begun. A run never outlives its worker, and nothing starts by itself at the next launch; a run the user starts while the worker is still coming up is left alone.
- The plugin is never imported into the API or the worker. The test that proves it spawns a process whose pid is not the worker's.

## Acceptance

- A run of `plugins/example` with input `hi` exits 0, and a note with that content exists in the run's workspace. The run status is `succeeded`.
- A plugin that exits 1: status `failed`, worker process still alive.
- A plugin that adds two documents and then raises: status `failed`, and both documents are there.
- Cancel mid-run: status `cancelled` within ten seconds, and neither the plugin's pid nor a child it spawned is still alive.
- A plugin whose action sets `timeout_seconds: 2` and sleeps for ten: status `failed` with `timeout`.
- Killing the worker's process group while a plugin runs leaves no plugin process behind. On the worker's next start the run is `failed` with `interrupted`.
- Deleting a workspace while a plugin runs in it stops the plugin and every process it started first; then the workspace, its documents and the run's record are gone.
- With four runs going, a fifth is `queued` and starts when one ends. Cancelling it while `queued` never spawns it.
- A plugin spawned without `SURFSENSE_PLUGIN_API_URL` fails with the SDK's own message rather than a connection error.
- A plugin's environment holds no `SURFSENSE_LOCAL_` variable, and its secrets appear in no file the run wrote.
- A plugin with its own `json.py` still gets the standard library's `json`, and so does the SDK.
- A plugin that exits with `sys.exit("Token expired")`: status `failed`, `error` `exit 1`, and `Token expired` in the log tail.

## Needs from

The protocol. `plugins/example` from the SDK stream for the success test, and a running API for any test that exercises a verb. A one-file fake plugin in this stream's tests is enough for spawn, cancel, timeout and crash, so this stream does not wait on the SDK.
