# SDK — library

> Owns: `plugins/bundles/core/sdk/`, including its contract tests. Authors run plugins on it with `surfsense-plugins invoke` ([`../cli/01-author-commands.md`](../cli/01-author-commands.md)).
> Contract: [`../01-protocol.md`](../01-protocol.md). How it grows: [`../02-extending.md`](../02-extending.md).

## Goal

The SDK is the seam between every plugin and the app, so both of its sides are checked on every change: its types against every plugin, its calls against the real app.

## Work

- Package `surfsense_plugin_sdk` in `plugins/bundles/core/sdk/`, a project of its own, `plugins/bundles/core/sdk/pyproject.toml`, with no dependencies. `run/__main__.py`, run as `python -S -m surfsense_plugin_sdk.run`, reads the arguments from the protocol, puts the plugin's own directory and its `site-packages` on the path as the protocol says, calls the matching `@action` function, and exits 0 or 1.
- Strictly typed. Every public function is annotated, the package ships a `py.typed` marker, `__all__` lists exactly what is public, and nothing public is typed `Any` except `Response.json()`, whose shape comes from the source, not the SDK. Verbs return typed objects, such as `Document`, rather than dictionaries. pyright checks the SDK in strict mode, and the checks type-check every plugin against it ([`../release/02-pull-request-checks.md`](../release/02-pull-request-checks.md)).
- Context accessors, one file each: `action`, `secret`, `data`. `action` passes the inputs to the function as keyword arguments. `secret` reads `SURFSENSE_PLUGIN_SECRET_<NAME>` and raises by name when it is undeclared or absent.
- `http/`: `get`, `post` and `request` on the standard library, one file each for the host check, redirects, headers, the response and sending. It reads `hosts` from the plugin's own `manifest.json`, checks the host before every connection and every redirect, and raises `HostNotDeclared` naming the host. A redirect to another host drops `Authorization` and `Cookie`. Requests name the plugin in `User-Agent` unless the author sets one, since sources often refuse Python's own. Response headers are found however a name is written. One log line per request: method, host, status, or the reason it failed, and a failed connection raises `ConnectionError` naming the host. A default timeout per request, so a silent server fails the call rather than the whole run. Certificates are verified by the standard library against the system's certificate file, which the bundled Python finds on all three systems: `/etc/ssl` on Linux, `/private/etc/ssl` on macOS, the system store on Windows. The SDK depends on nothing.
- `app/client.py` holds the one HTTP client the verbs share, bound to `SURFSENSE_PLUGIN_API_URL`, and never through the user's proxy, which cannot reach loopback. It raises with the app's own message on a failure, and raises something an author can act on when the variable is absent — that is the message an author who runs a plugin with no app will see. It does not go through `http`: loopback is not egress.
- The verbs, one file per domain in `app/`, beside the client they share. v1 is `app/document.py`: `add`, `list` and `update`, complete per [`../02-extending.md`](../02-extending.md). `add` stamps the note's provenance, with the keys and sources [`../app/01-api.md`](../app/01-api.md) lists. Verbs default the workspace, run, and plugin ids from the environment and return what they created. `workspace`, `artifact` and `model` wait for their app routes.
- Contract tests in `plugins/bundles/core/sdk/tests/contract/`: each public verb called against the real backend, started on a temporary data directory, asserting what the app did and what the verb returned. A route that changes under a verb fails here, on the pull request that changed it. One test lists `__all__` and fails when a public verb has no contract test, so coverage is enforced rather than remembered.
## Acceptance

- A plugin whose action raises exits non-zero, and anything it committed before the exception is still in the app.
- A verb called with no `SURFSENSE_PLUGIN_API_URL` raises a message naming `surfsense-plugins invoke` and its `--api-url`, not a connection error.
- `secret` with the variable set, and without it, and for a name the manifest does not declare.
- `http.get` to a declared host reaches it and logs one line with no path. To an undeclared host it raises `HostNotDeclared` and opens no connection. A declared host that redirects to an undeclared one raises on the redirect.
- A dependency whose package ships a `.pth` file has it processed.
- The SDK passes pyright in strict mode, and nothing in `__all__` is typed `Any` but `Response.json()`.
- Every verb in `__all__` has a contract test; removing one fails the coverage test.

## Testing

Verbs and `http` are unit-tested against a stub app: a `ThreadingHTTPServer` on `127.0.0.1:0` in `conftest`, the pattern `backend/tests/integration/chat/conftest.py` already uses. Those tests assert the request the verb made and the value it returned. The contract tests then prove the real app still answers that request that way.

## Needs from

Nothing in the app to build against a stub. The contract tests need the API up. Until [`../python/01-interpreter.md`](../python/01-interpreter.md) lands, `python` is `uv run` from `plugins/bundles/core/sdk`.
