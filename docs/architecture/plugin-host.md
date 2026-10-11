# Plugin host

The plugin host is the one server that will run SurfSense's own plugins, free and paid, each an MCP server at `/<id>/mcp`. It is apart from `surfsense_backend` and the desktop app, and imports neither. So far it serves `/health` and whatever plugin folders exist, and checks the SurfSense license for paid ones; no plugin is written yet, and it is not deployed ([proposal](../proposals/plugins/remote/02-surfsense-servers.md)).

**Code:** [`plugins/remote/`](../../plugins/remote/)
**Decisions:** [ADR 0054](../adr/0054-surfsenses-plugins-run-on-one-plugin-host.md), [ADR 0047](../adr/0047-premium-plugins-are-source-available.md)

## Layout

`plugins/remote/` is the import root: code imports `host.app`, `mcp_server.access` or `proprietary.license_check`.

| Folder | License | Holds |
|---|---|---|
| [`host/`](../../plugins/remote/host/) | Apache-2.0 | The server, its `pyproject.toml` and `uv.lock` for every plugin's dependencies, and the tests of the host |
| [`mcp_server/`](../../plugins/remote/mcp_server/) | Apache-2.0 | What a plugin builds on: [`access.py`](../../plugins/remote/mcp_server/access.py), the hook a paid plugin's check plugs into |
| `<id>/` | Apache-2.0 | A free plugin (none yet) |
| [`proprietary/`](../../plugins/remote/proprietary/) | Business Source License 1.1 | Paid plugins (none yet) and [`license_check/`](../../plugins/remote/proprietary/license_check/) |

The license check is `license_check/`, not `license/`: a `license/` folder beside the `LICENSE` file is one path on macOS and Windows.

## Serving plugins

[`host_app()`](../../plugins/remote/host/app.py) mounts each plugin and answers `GET /health` with `ok`.

- A plugin is a folder with a `server.py` whose `server()` returns its `MCPServer`, from the official MCP Python SDK: its own MCP server at its own path. The folder's name, with underscores as hyphens, is its id and its path: `proprietary/google_search/` would be served at `/google-search/mcp`, since a Python package cannot hold a hyphen ([`mounted_plugins.py`](../../plugins/remote/host/mounted_plugins.py)).
- Folders under the root and under `proprietary/` are both read. Without `proprietary/`, the open build, the host serves the Apache-2.0 plugins and has nothing else missing.
- `host`, `mcp_server`, `proprietary`, `license_check` and `scraping`, the code the scraper plugins will share, are never plugin ids. Two plugins with one id stop the host from starting.
- A tool that raises returns an MCP error for that call; the other plugins keep answering.
- The SDK's DNS-rebinding guard is off: it protects servers on a user's loopback, and the host is reached by its public name.

`python -m host`, run from `plugins/remote/`, serves on `PORT`, 8000 by default.

## The license check

A plugin's `server.py` may set `access`, an object with `refusal(headers)` ([`access.py`](../../plugins/remote/mcp_server/access.py)). The host asks it before every request reaches the plugin, and answers a refusal itself with its status and `{"reason": ...}` ([`refused_unless_allowed.py`](../../plugins/remote/host/refused_unless_allowed.py)). A plugin without `access` is open: SurfSense offers no free plugin yet, and nothing limits an open one per IP address ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#adding-a-plugin)).

A paid plugin sets `access = LicenseAccess()` ([`license_access.py`](../../plugins/remote/proprietary/license_check/license_access.py)), which applies [contract 2](../contracts/02-scraper-api-auth.md):

| Request | Answer |
|---|---|
| No `Authorization: License <key>`, another scheme, or an empty key | `401 missing_license`, without asking Keygen |
| Keygen says `VALID` | Through to the plugin |
| `EXPIRED` | `403 expired` |
| `SUSPENDED` or `BANNED` (a refund suspends) | `403 revoked` |
| `NOT_FOUND` or any other code | `403 invalid` |
| Keygen unreachable or answering 5xx, key valid in the last 24 hours | Through to the plugin |
| Keygen unreachable, key not valid in the last 24 hours | `503 license_service_unavailable` |

- Keygen is asked about a key at most once in five minutes; the answer, refusal or not, is kept that long.
- The check uses Keygen's `validate-key` action ([`keygen.py`](../../plugins/remote/proprietary/license_check/keygen.py)), which takes no token: the key is the credential, so the host holds no Keygen secret. Keygen's address and SurfSense's account id are constants in that file, not settings.

## Tests

From `plugins/remote/host`: `uv run pytest`, `uv run ruff check ..` and `uv run ruff format --check ..`. The lint includes ruff's `ASYNC` rules, which fail a blocking call inside an `async def`, since every plugin answers from one process. CI runs them in `plugins-pull-request-checks.yml` when `plugins/remote/` changes.

- [`host/tests/`](../../plugins/remote/host/tests/) serve sample plugins on loopback and reach them with the official MCP client: the health check, each plugin at its path, the build without `proprietary/`, a failing tool, an underscored folder at its hyphenated id, and reserved folders.
- [`proprietary/license_check/tests/`](../../plugins/remote/proprietary/license_check/tests/) check the license against a stand-in Keygen on loopback, with the clock passed in: each answer above, the five-minute cache, the 24-hour grace, and a paid sample plugin through the host.

## Known gaps

- `SURFSENSE_ACCOUNT_ID` in `keygen.py` is empty, so a paid plugin's `LicenseAccess()` stops the host from starting until it is set.
- No plugin exists: the scraper plugins, one per platform, are still in `surfsense_backend` ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#the-scraper-plugins)).
- No limit on threads or browsers per plugin, and no per-IP limit for a free plugin, since none exists.
- Requests are not counted or rate-limited per license. License answers and the 24-hour grace are kept per replica, in memory, not in Redis, so a deploy during a Keygen outage refuses keys that were valid.
- No deadline on a plugin's call and no MCP progress. Long calls and large results do not run as jobs, and there is no job runner, Redis or Blob Storage ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#long-calls-run-as-jobs)).
- MCP is served with sessions kept in memory, so only one copy of the host can run, and there is no cancel route or `PLUGINS` setting yet ([proposal](../proposals/plugins/remote/02-surfsense-servers.md#scaling)).
- No registry files, Docker image or Azure deployment.
