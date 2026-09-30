# SDK — library and harness

> Owns: `plugins/core/sdk/`, including its contract tests, `plugins/example/`, `plugins/README.md`.
> Contract: [`../01-protocol.md`](../01-protocol.md). How it grows: [`../02-extending.md`](../02-extending.md).

## Goal

An author runs a plugin on her machine, against the real protocol and a real app, without Electron and without the frozen binaries. The SDK is the seam between every plugin and the app, so both of its sides are checked on every change: its types against every plugin, its calls against the real app.

## Work

- Package `surfsense_plugin_sdk` in `plugins/core/sdk/`, a project of its own, `plugins/core/sdk/pyproject.toml`, with no dependencies, for its tests and the harness. `run/__main__.py`, run as `python -m surfsense_plugin_sdk.run`, reads the arguments from the protocol, puts the plugin's own directory and its `site-packages` on the path as the protocol says, calls the matching `@action` function, and exits 0 or 1.
- Strictly typed. Every public function is annotated, the package ships a `py.typed` marker, `__all__` lists exactly what is public, and nothing public is typed `Any` except `Response.json()`, whose shape comes from the source, not the SDK. Verbs return typed objects, such as `Document`, rather than dictionaries. pyright checks the SDK in strict mode, and the checks type-check every plugin against it ([`../release/02-pull-request-checks.md`](../release/02-pull-request-checks.md)).
- Context accessors, one file each: `action`, `secret`, `data`. `action` passes the inputs to the function as keyword arguments. `secret` reads `SURFSENSE_PLUGIN_SECRET_<NAME>` and raises by name when it is undeclared or absent.
- `http/`: `get`, `post` and `request` on the standard library, one file each for the host check, redirects, headers, the response and sending. It reads `hosts` from the plugin's own `manifest.json`, checks the host before every connection and every redirect, and raises `HostNotDeclared` naming the host. A redirect to another host drops `Authorization` and `Cookie`, as `requests` does. Requests name the plugin in `User-Agent` unless the author sets one, since sources often refuse Python's own. Response headers are found however a name is written. One log line per request: method, host, status, or the reason it failed, and a failed connection raises `ConnectionError` naming the host. A default timeout per request, so a silent server fails the call rather than the whole run. Certificates are verified by the standard library against the system's certificate file, which the bundled Python finds on all three systems: `/etc/ssl` on Linux, `/private/etc/ssl` on macOS, the system store on Windows. The SDK depends on nothing.
- `app/client.py` holds the one HTTP client the verbs share, bound to `SURFSENSE_PLUGIN_API_URL`, and never through the user's proxy, which cannot reach loopback. It raises with the app's own message on a failure, and raises something an author can act on when the variable is absent — that is the message someone running the harness with no app will see. It does not go through `http`: loopback is not egress.
- The verbs, one file per domain in `app/`, beside the client they share. v1 is `app/document.py`: `add`, `list` and `update`, complete per [`../02-extending.md`](../02-extending.md). `add` stamps the note's provenance, with the keys and sources [`../app/01-api.md`](../app/01-api.md) lists. Verbs default the workspace, run, and plugin ids from the environment and return what they created. `workspace`, `artifact` and `model` wait for their app routes.
- Contract tests in `plugins/core/sdk/tests/contract/`: each public verb called against the real backend, started on a temporary data directory, asserting what the app did and what the verb returned. A route that changes under a verb fails here, on the pull request that changed it. One test lists `__all__` and fails when a public verb has no contract test, so coverage is enforced rather than remembered. VS Code tests its own extension API the same way, with the `vscode-api-tests` suite running inside the app.
- `python -m surfsense_plugin_sdk.harness`. It lays down the same files, spawns the same command, and exits with the run's code. It finds the app at `--api-url`, else `SURFSENSE_PLUGIN_API_URL`, else `~/.surfsense-dev/api-url`, which a development app writes, else `~/.surfsense/api-url`, which a packaged app writes. Inputs come from `--input name=value`, and secrets from the author's own `SURFSENSE_PLUGIN_SECRET_<NAME>` variables or a hidden prompt, never from a flag, so they stay out of shell history. For a plugin with dependencies it first installs `requirements.txt` into `plugins/<id>/site-packages/`, for the author's own platform, the way packaging does ([`../release/01-packaging.md`](../release/01-packaging.md)). The root `.gitignore` ignores `plugins/*/site-packages/`. It does not intercept HTTP and it does not stub the app.
- `plugins/example/`. `access: free`, `hosts: []`, no secrets, one action `echo` with a required string input `text`, no requirements. The action calls `document.add()` with the input as the content. This is the plugin the other streams' tests run. It is not a product plugin.
- `plugins/README.md` is the contributor guide. It points at `plugins/example` instead of pasting a second copy of it, and covers:
  - the folder layout and every `manifest.json` field, including `platforms` and `timeout_seconds`. Beyond a small `main.py`, put the code in a package named after the plugin, such as `hn_search/`, so no file of yours can clash with a standard-library module or a dependency;
  - what to ask the user and where: an input when it changes every run, a secret for anything that must not be shown again. Never ask for a secret as an input;
  - how inputs arrive: as keyword arguments named after the declared inputs, a `string` as `str`, a `number` as `int` or `float`, so annotate it `float`, a `boolean` as `bool`, and an optional input the user left empty as `None`, so annotate it `str | None` or the like;
  - the accessors, `http`, and the verbs, and that a failure is explained by writing the reason to stderr, which the user sees in the run's log;
  - that a plugin needing something the SDK lacks is welcome to propose it, as [`../02-extending.md`](../02-extending.md#growing-the-sdk-together) describes;
  - network: send every request through `http` and list every host it reaches, redirects included. Another client (`requests`, a browser) is not checked; say why in the pull request;
  - dependencies: prefer pure-Python packages, which ship as one small download for every system. A compiled one is fine if it publishes wheels for every platform in `plugins/core/build-targets.json`. Write `requirements.in`, generate `requirements.txt` with the protocol's command, never edit it by hand;
  - the harness command, and `surfsense-plugins check <plugin>`, which runs what CI runs, to use before opening a pull request;
  - releasing: you never write a version. A merged change ships with the next SurfSense release, stamped with its version, and the directory site shows it once that release is published ([`../04-versioning.md`](../04-versioning.md));
  - the data directory survives updates, and an app can move a plugin back to an older version when a newer one is blocked, so read data written by a newer version carefully, or start over. It is also shared by every workspace: to know what is already in the run's workspace, call `document.list()`, and keep in the data directory what belongs to the plugin itself, such as a cache or the time it last fetched.

## Acceptance

- `python -m surfsense_plugin_sdk.harness plugins/example echo --input text=hi` against a running app exits 0 and leaves one note whose content is `hi`.
- A plugin whose action raises exits non-zero, and anything it committed before the exception is still in the app.
- A verb called with no `SURFSENSE_PLUGIN_API_URL` raises a message naming the harness flag, not a connection error.
- `secret` with the variable set, and without it, and for a name the manifest does not declare.
- `http.get` to a declared host reaches it and logs one line with no path. To an undeclared host it raises `HostNotDeclared` and opens no connection. A declared host that redirects to an undeclared one raises on the redirect.
- A dependency whose package ships a `.pth` file has it processed.
- The SDK passes pyright in strict mode, and nothing in `__all__` is typed `Any` but `Response.json()`.
- Every verb in `__all__` has a contract test; removing one fails the coverage test.
- The example plugin's `main.py` imports only `surfsense_plugin_sdk`.

## Testing

Verbs and `http` are unit-tested against a stub app: a `ThreadingHTTPServer` on `127.0.0.1:0` in `conftest`, the pattern `backend/tests/integration/chat/conftest.py` already uses. Those tests assert the request the verb made and the value it returned. The contract tests then prove the real app still answers that request that way.

## Needs from

Nothing in the app to build against a stub. The contract tests and the acceptance run need the API up, and `api-url` needs Electron to write it ([`../runtime/01-process.md`](../runtime/01-process.md) and the app stream). Until [`../python/01-interpreter.md`](../python/01-interpreter.md) lands, `python` is `uv run` from `plugins/core/sdk`.
