# SDK — library and harness

> Owns: `plugins/sdk/`, `plugins/example/`, `plugins/README.md`.
> Contract: [`../01-protocol.md`](../01-protocol.md). How it grows: [`../02-extending.md`](../02-extending.md).

## Goal

An author runs a plugin on her machine, against the real protocol and a real app, without Electron and without the frozen binaries.

## Work

- Package `surfsense_plugin` in `plugins/sdk/`. `__main__` reads the arguments from the protocol, puts the plugin's own directory and its `site-packages` on the path as the protocol says, calls the matching `@entry` function, and exits 0 or 1.
- Context accessors, one file each: `entry`, `secret`, `data`. `entry` passes the inputs to the function as keyword arguments. `secret` reads `SURFSENSE_PLUGIN_SECRET_<NAME>` and raises by name when it is undeclared or absent.
- `http.py`: `get`, `post` and `request` on the standard library. It reads `hosts` from the plugin's own `plugin.json`, checks the host before every connection and every redirect, and raises `HostNotDeclared` naming the host. One log line per request: method, host, status. A default timeout per request, so a silent server fails the call rather than the whole run. Certificates are verified by the standard library against the system's certificate file, which the bundled Python finds on all three systems: `/etc/ssl` on Linux, `/private/etc/ssl` on macOS, the system store on Windows. The SDK depends on nothing.
- `client.py` holds the one HTTP client the verbs share, bound to `SURFSENSE_PLUGIN_API_URL`. It raises with the app's own message on a failure, and raises something an author can act on when the variable is absent — that is the message someone running the harness with no app will see. It does not go through `http`: loopback is not egress.
- The verbs, one file per domain. v1 is `document.py`: `add`, `list` and `update`, complete per [`../02-extending.md`](../02-extending.md). `add` stamps the note's provenance, with the keys and sources [`../app/01-api.md`](../app/01-api.md) lists. Verbs default the workspace, run, and plugin ids from the environment and return what they created. `workspace`, `artifact` and `model` wait for their app routes.
- `plugins/sdk/VERSION`, the one place the SDK's version lives, starting at `1.0.0`; `__init__` reads it into `__version__`.
- `python -m surfsense_plugin.harness`. It lays down the same files, spawns the same command, and exits with the run's code. It finds the app at `--api-url`, else `SURFSENSE_PLUGIN_API_URL`, else `~/.surfsense/api-url`, which Electron writes when it picks the port. Inputs come from `--input name=value`, and secrets from the author's own `SURFSENSE_PLUGIN_SECRET_<NAME>` variables or a hidden prompt, never from a flag, so they stay out of shell history. For a plugin with dependencies it first installs `requirements.txt` into `plugins/<id>/site-packages/`, for the author's own platform, with the Python version in `plugins/targets.json` and the flags `plugins/build/` uses. The root `.gitignore` ignores `plugins/*/site-packages/`. It does not intercept HTTP and it does not stub the app.
- `plugins/example/`. `access: free`, `hosts: []`, no secrets, one entry `echo` with a required string input `text`, no requirements. The entry calls `document.add()` with the input as the content. This is the plugin the other streams' tests run. It is not a product plugin.
- `plugins/README.md` is the contributor guide. It points at `plugins/example` instead of pasting a second copy of it, and covers:
  - the folder layout and every `plugin.json` field, including `platforms` and `timeout_seconds`. Beyond a small `main.py`, put the code in a package named after the plugin, such as `hn_search/`, so no file of yours can clash with a standard-library module or a dependency;
  - what to ask the user and where: an input when it changes every run, a secret for anything that must not be shown again. Never ask for a secret as an input;
  - the accessors, `http`, and the verbs, and that a failure is explained by writing the reason to stderr, which the user sees in the run's log;
  - that a plugin needing something the SDK lacks is welcome to propose it, as [`../02-extending.md`](../02-extending.md#growing-the-sdk-together) describes;
  - network: send every request through `http` and list every host it reaches, redirects included. Another client (`requests`, a browser) is not checked; say why in the pull request;
  - dependencies: prefer pure-Python packages, which ship as one small download for every system. A compiled one is fine if it publishes wheels for every platform in `plugins/targets.json`. Write `requirements.in`, generate `requirements.txt` with the protocol's command, never edit it by hand;
  - the harness command, and the `check` command from [`../catalog/01-manifest-and-ci.md`](../catalog/01-manifest-and-ci.md), which runs what CI runs, to use before opening a pull request;
  - releasing: a pull request that changes a plugin raises its version, and merging it publishes that version.

## Acceptance

- `python -m surfsense_plugin.harness plugins/example echo --input text=hi` against a running app exits 0 and leaves one note whose content is `hi`.
- A plugin whose entry raises exits non-zero, and anything it committed before the exception is still in the app.
- A verb called with no `SURFSENSE_PLUGIN_API_URL` raises a message naming the harness flag, not a connection error.
- `secret` with the variable set, and without it, and for a name the manifest does not declare.
- `http.get` to a declared host reaches it and logs one line with no path. To an undeclared host it raises `HostNotDeclared` and opens no connection. A declared host that redirects to an undeclared one raises on the redirect.
- A dependency whose package ships a `.pth` file has it processed.
- The example plugin's `main.py` imports only `surfsense_plugin`.

## Testing

Verbs and `http` are tested against a stub app: a `ThreadingHTTPServer` on `127.0.0.1:0` in `conftest`, the pattern `backend/tests/integration/chat/conftest.py` already uses. Tests assert the request the verb made and the value it returned, so a route change is caught here rather than in a plugin.

## Needs from

Nothing in the app to build against a stub. The acceptance run needs the API up, and `~/.surfsense/api-url` needs Electron to write it ([`../runtime/01-process.md`](../runtime/01-process.md) and the app stream). Until [`../python/01-interpreter.md`](../python/01-interpreter.md) lands, `python` is `uv run` from `plugins/sdk`.
