# SDK — library and harness

> Owns: `plugins/sdk/`, `plugins/example/`, `plugins/README.md`.
> Contract: [`../01-protocol.md`](../01-protocol.md). How it grows: [`../02-extending.md`](../02-extending.md).

## Goal

An author runs a plugin on her machine, against the real protocol and a real app, without Electron and without the frozen binaries.

## Work

- Package `surfsense_plugin` in `plugins/sdk/`. `__main__` reads the arguments from the protocol, calls the matching `@entry` function, and exits 0 or 1.
- Context accessors, one file each: `entry`, `secret`, `data`. `secret` reads `SURFSENSE_PLUGIN_SECRET_<NAME>` and raises by name when it is absent.
- `client.py` holds the one HTTP client the verbs share, bound to `SURFSENSE_PLUGIN_API_URL`. It raises with the app's own message on a failure, and raises something an author can act on when the variable is absent — that is the message someone running the harness with no app will see.
- The verbs, one file per domain: `workspace`, `document`, `artifact`, `model`. Complete within each, per [`../02-extending.md`](../02-extending.md). They default the workspace, run, and plugin ids from the environment and return what they created.
- `python -m surfsense_plugin.harness`. It lays down the same files, spawns the same command, and exits with the run's code. It finds the app at `--api-url`, else `SURFSENSE_PLUGIN_API_URL`, else `~/.surfsense/api-url`, which Electron writes when it picks the port. It does not intercept HTTP and it does not stub the app.
- `plugins/example/`. `license: free`, `hosts: []`, one entry `echo` with a string input `text`, no requirements. The entry calls `document.add()` with the input as the content. This is the plugin the other streams' tests run. It is not a product plugin.
- `plugins/README.md` is the contributor guide: the folder layout, `plugin.json` fields, the accessors and the verbs, the harness command, how a pull request is checked, and the fact that `requirements.txt` is installed by CI rather than on the user's machine. Point at `plugins/example` instead of pasting a second copy of it.

## Acceptance

- `python -m surfsense_plugin.harness plugins/example echo --input text=hi` against a running app exits 0 and leaves one note whose content is `hi`.
- A plugin whose entry raises exits non-zero, and anything it committed before the exception is still in the app.
- A verb called with no `SURFSENSE_PLUGIN_API_URL` raises a message naming the harness flag, not a connection error.
- `secret` with the variable set, and without it.
- The example plugin's `main.py` imports only `surfsense_plugin`.

## Testing

Verbs are tested against a stub app: a `ThreadingHTTPServer` on `127.0.0.1:0` in `conftest`, the pattern `backend/tests/integration/chat/conftest.py` already uses. Tests assert the request the verb made and the value it returned, so a route change is caught here rather than in a plugin.

## Needs from

Nothing in the app to build against a stub. The acceptance run needs the API up, and `~/.surfsense/api-url` needs Electron to write it ([`../runtime/01-process.md`](../runtime/01-process.md) and the app stream). Until [`../python/01-interpreter.md`](../python/01-interpreter.md) lands, `python` is `uv run` from `plugins/sdk`.
