# Runtime — process

> Owns: `surfsense_local/backend/modules/plugins/runner.py`, `modules/plugins/tasks.py`, the `plugin_runs` table.
> Contract: [`../01-protocol.md`](../01-protocol.md).

## Goal

The worker starts a plugin process for one run and records how it ended. [`02-calls-and-results.md`](02-calls-and-results.md) reads the results file afterward.

## Work

- Hand-written migration for `plugin_runs`: `id`, `workspace_id`, `plugin_id`, `entry`, `inputs` JSON, `status` (`running` `succeeded` `failed` `cancelled`), `error`, `log_tail`, `started_at`, `finished_at`.
- `import_models()` and `import_tasks()` gain this module the same way the other modules do. A test in the existing registration test fails if they are missing.
- Huey task `run_plugin(run_id)`. The API enqueues it. The task spawns the interpreter from `plugin_python()` ([`../python/01-interpreter.md`](../python/01-interpreter.md) supplies the packaged path; until then the task accepts an explicit interpreter path and tests pass `sys.executable`).
- Arguments, as the protocol specifies: `<plugin-dir> <entry> --inputs <file> --results <file> --data <dir>`. The task writes the inputs file and an empty results file. Working directory is the plugin directory. `PYTHONPATH` is the SDK directory shipped next to the interpreter, then `<plugin-dir>/site-packages` when that directory exists. The SDK is not installed from PyPI and is not inside the tarball.
- For each manifest secret, set `SURFSENSE_PLUGIN_SECRET_<NAME>`. The API has already refused the run when one is missing, or when a host in `hosts` has not been allowed.
- Capture stdout and stderr into a ring of 16 KiB on `log_tail`.
- Exit 0 sets `succeeded`. Any other exit sets `failed` with `error` `exit <code>`. Either way, hand the results path to the import in [`02-calls-and-results.md`](02-calls-and-results.md).
- Cancel sets a flag the task watches. The task sends `SIGTERM`, waits five seconds, sends `SIGKILL`, sets `cancelled`. Do not add a process-count limit.
- The plugin is never imported into the API or the worker. The test that proves it spawns a process whose pid is not the worker's.

## Acceptance

- A run of `plugins/example` with input `hi` exits 0 and leaves one results line. The run status is `succeeded`.
- A plugin that exits 1: status `failed`, worker process still alive.
- Cancel mid-run: status `cancelled` within ten seconds, and the pid is gone.

## Needs from

The protocol. `plugins/example` from the SDK stream for the success test. A one-file fake plugin in this stream's tests is enough for handshake, cancel, and crash, so this stream does not wait on the SDK.
