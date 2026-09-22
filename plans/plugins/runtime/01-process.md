# Runtime — process

> Owns: `surfsense_local/backend/modules/plugins/runner.py`, `modules/plugins/tasks.py`, the `plugin_runs` table.
> Contract: [`../01-protocol.md`](../01-protocol.md).

## Goal

The worker starts a plugin process for one run, hands it its context, and records how it ended. There is nothing to import afterwards: the plugin wrote through the app's API while it ran.

## Work

- Hand-written migration for `plugin_runs`: `id`, `workspace_id`, `plugin_id`, `entry`, `inputs` JSON, `status` (`running` `succeeded` `failed` `cancelled`), `error`, `log_tail`, `started_at`, `finished_at`.
- `import_models()` and `import_tasks()` gain this module the same way the other modules do. A test in the existing registration test fails if they are missing.
- Huey task `run_plugin(run_id)`. The API enqueues it. The task spawns the interpreter from `plugin_python()` ([`../python/01-interpreter.md`](../python/01-interpreter.md) supplies the packaged path; until then the task accepts an explicit interpreter path and tests pass `sys.executable`).
- Arguments, as the protocol specifies: `<plugin-dir> <entry> --inputs <file> --data <dir>`. The task writes the inputs file. Working directory is the plugin directory. `PYTHONPATH` is the SDK directory shipped next to the interpreter; the SDK adds `<plugin-dir>` and its `site-packages` itself.
- Context in the environment: `SURFSENSE_PLUGIN_API_URL`, `SURFSENSE_PLUGIN_WORKSPACE_ID`, `SURFSENSE_PLUGIN_RUN_ID`, `SURFSENSE_PLUGIN_ID`, and one `SURFSENSE_PLUGIN_SECRET_<NAME>` per manifest secret. The API has already refused the run when a declared secret is missing.
- The API URL is the worker's own: Electron passes `SURFSENSE_LOCAL_HOST` and `SURFSENSE_LOCAL_PORT` to this process already (`electron/src/main/sidecars/python.ts`), so build it from those rather than inventing a second source of truth.
- Capture stdout and stderr into a ring of 16 KiB on `log_tail`.
- Exit 0 sets `succeeded`. Any other exit sets `failed` with `error` of `exit <code>`.
- Cancel sets a flag the task watches. The task sends `SIGTERM`, waits five seconds, sends `SIGKILL`, sets `cancelled`. Whatever the plugin already committed through the API stays, because it was committed when the call returned. Do not add a process-count limit.
- The plugin is never imported into the API or the worker. The test that proves it spawns a process whose pid is not the worker's.

## Acceptance

- A run of `plugins/example` with input `hi` exits 0, and a note with that content exists in the run's workspace. The run status is `succeeded`.
- A plugin that exits 1: status `failed`, worker process still alive.
- A plugin that adds two documents and then raises: status `failed`, and both documents are there.
- Cancel mid-run: status `cancelled` within ten seconds, and the pid is gone.
- A plugin spawned without `SURFSENSE_PLUGIN_API_URL` fails with the SDK's own message rather than a connection error.

## Needs from

The protocol. `plugins/example` from the SDK stream for the success test, and a running API for any test that exercises a verb. A one-file fake plugin in this stream's tests is enough for spawn, cancel, and crash, so this stream does not wait on the SDK.
