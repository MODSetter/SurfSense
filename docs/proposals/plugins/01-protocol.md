# Protocol

The contract the SDK, the runtime, the catalog, and the app all implement. A change here is a change to every stream.

Version is `1`. The `sdk` range in a manifest is how a plugin says which version of the surface it was written against. Adding to that surface is additive. Changing or removing anything in it is a bump.

The SDK's version lives in one file, `plugins/sdk/VERSION`, semver, starting at `1.0.0`. The SDK reports it as `surfsense_plugin.__version__`, and the app reads the same file from the SDK folder it ships. A new verb, domain or context variable raises the minor version; anything [`02-extending.md`](02-extending.md) calls not additive raises the major.

## On disk

```
plugins/<id>/
  plugin.json
  main.py             # where the SDK starts; it imports the rest
  <package>/          # optional: the plugin's own code, split as it likes
  requirements.in     # omitted when there are no dependencies
  requirements.txt    # generated from requirements.in, never edited by hand
  README.md           # optional: for readers on GitHub; the app shows `description`
  tests/              # optional
  fixtures/           # optional
```

A plugin carries no license of its own. Like everything outside `surfsense_backend/app/proprietary/`, it is Apache-2.0 under the repository's [`LICENSE`](../../../LICENSE), and a pull request's contribution is Apache-2.0 by section 5 of that license. `access` is a different thing: whether running the plugin needs a SurfSense license file.

`main.py` is only the entry point. A plugin may be any number of modules and packages, and any data files it reads; the tarball carries the whole folder. The SDK imports `main.py`, so an `@entry` function defined elsewhere must be imported from it. A top-level module named like a standard-library module or a dependency fails the check, because the path order would ignore it or let it hide the library; code in a package named after the plugin never clashes.

`site-packages/` is never in git. CI creates it inside each tarball, and the harness creates a git-ignored one on the author's machine.

### Dependencies

`requirements.in` names what the plugin imports. `requirements.txt` is generated from it, and it is what pins:

```
uv pip compile --universal --generate-hashes --python-version 3.12 requirements.in -o requirements.txt
```

It pins every transitive dependency for every platform, with a sha256 per file, so the files CI installs are the files review saw. PyPI only, prebuilt wheels only: no URLs, no editable installs, no index options, and no source distributions, because a Linux runner cannot compile one for Windows or macOS.

### `plugin.json`

| Field | Rule |
|---|---|
| `id` | Equals the folder name. Pattern above. |
| `name` | Display string, 1–80 characters. |
| `description` | One line for the catalog card, 1–200 characters. |
| `author` | Display string. Not unique. |
| `version` | Semver `MAJOR.MINOR.PATCH`. |
| `sdk` | A PEP 440 specifier. The app's SDK version must satisfy it or the plugin does not install and the run does not start. |
| `access` | `free` or `paid`. Only a reserved id may be `paid`. |
| `hosts` | Array of exact hostnames: no scheme, path, port or wildcard, and never a loopback name. Shown in the catalog. Each one needs the user's consent before the plugin's first run, and the SDK's `http` refuses any host not listed. |
| `secrets` | Optional array of what the user enters once, in Settings, stored encrypted and never shown again: an API token, a password. Each is `{ "name", "title", "description" }`: `name` matches `^[a-z][a-z0-9_]{0,63}$` so it is a legal variable name, `title` is the label, and the optional `description` says where to get it. Every declared secret is required. Values are never in this file. |
| `platforms` | Optional. A non-empty subset of the platform keys in `plugins/targets.json`. Absent means all of them. On any other system the app does not list the plugin. |
| `entries` | At least one. |

An entry:

| Field | Rule |
|---|---|
| `name` | `^[a-z][a-z0-9-]{0,63}$`, unique within the plugin. |
| `title` | Display string. |
| `inputs` | Array, may be empty. The run dialog asks for them every run. Each is `{ "name", "title", "kind", "required" }`: `name` matches `^[a-z][a-z0-9_]{0,63}$` and is unique within the entry, `title` is the label, `kind` is `string`, `number`, or `boolean`, and `required` defaults to `false`. |
| `timeout_seconds` | Optional integer, 1 to 21600. Absent means 1800. A run still going at that point is stopped and fails. |

Unknown fields are ignored, so a future field does not break an older app. A missing required field, a bad id, or a second entry with the same name fails the manifest check.

### What the user provides

| The user provides | Asked | Kept | The plugin reads it with |
|---|---|---|---|
| An input | every run, in the run dialog | on the run's record | the entry function's arguments |
| A secret | once, in Settings, never shown again | encrypted through `shared/secrets.py` | `secret("name")` |

The app draws both forms from these declarations; a plugin never draws its own. Until every secret has a value, the plugin's sidebar actions are disabled, with a link to set them up. Raycast splits the same way: arguments per command, and preferences kept across runs, with `password` as one preference type.

More kinds of input, and settings that are not secret, come the way any capability does: with the first plugin that needs them ([`02-extending.md`](02-extending.md#growing-the-sdk-together)).

### Targets

`plugins/targets.json` is the one list of what plugins are built for: the CPython version the app ships, and each platform with the `uv` target that picks wheels old enough for the app's oldest supported systems, Ubuntu 22.04, RHEL 9 and macOS 13.3 ([packaging](../../architecture/packaging.md)).

```json
{
  "python": "3.12",
  "platforms": {
    "windows-x64": "x86_64-pc-windows-msvc",
    "macos-arm64": "aarch64-apple-darwin",
    "linux-x64": "x86_64-manylinux_2_34"
  }
}
```

The interpreter fetch script, the build tool and the checker all read it. There is no Intel Mac target ([ADR 0021](../../adr/0021-no-intel-mac-build.md)).

### Tarball

A download key is `any`, or `cp<major><minor>-<platform>` such as `cp312-linux-x64`, because compiled code runs only on the platform and the Python it was built for. CI builds one `any` tarball when the dependencies install to the same files on every target in `platforms`, and one tarball per target otherwise.

`<id>-<version>-<key>.tar.gz`. One top-level directory `<id>-<version>/` containing the folder above plus `site-packages/` when there are dependencies. The `plugin.json` inside the tarball must deep-equal the catalog entry's manifest fields (`id`, `name`, `description`, `author`, `version`, `sdk`, `access`, `hosts`, `secrets`, `platforms`, `entries`). A mismatch rejects the install. The sha256 is of the gzip bytes, and it is also the file's address in the registry. A tarball is at most 100 MB unless `plugins/SIZE-EXCEPTIONS` names the plugin.

A published version never changes. Publishing a version that already exists fails.

Extraction rejects any member whose path is absolute, contains `..`, or is a link that resolves outside the destination. The destination is `<data>/plugins/<id>/<version>.tmp-<pid>/`, then one rename to `<data>/plugins/<id>/<version>/`. One version stays on disk: once a new one is in place, the previous directory is deleted.

### Catalog

One JSON file, `catalog.json`:

```json
{
  "generated_at": "2026-10-01T12:00:00Z",
  "plugins": [
    {
      "id": "example",
      "name": "Example",
      "description": "Adds the text you type as a note.",
      "author": "SurfSense",
      "version": "1.1.0",
      "sdk": ">=1,<2",
      "access": "free",
      "hosts": [],
      "secrets": [],
      "entries": [
        {
          "name": "echo",
          "title": "Echo",
          "inputs": [{ "name": "text", "title": "Text", "kind": "string", "required": true }]
        }
      ],
      "downloads": {
        "any": {
          "url": "https://ghcr.io/v2/modsetter/surfsense/plugins/example/blobs/sha256:<64 hex>",
          "sha256": "<64 hex>",
          "size": 18231
        }
      },
      "yanked": { "1.0.0": "Wrote every note twice. Fixed in 1.1.0." }
    }
  ]
}
```

- One entry per plugin, at its latest version.
- The app takes the download for its own key, else `any`. With neither, it cannot install the plugin and does not list it.
- `yanked` maps a withdrawn version to the reason shown to the user. It survives later versions, so an installed copy of a withdrawn version stays refused after a fix ships.
- Every `url` starts with `https://ghcr.io/v2/modsetter/surfsense/plugins/`. The app drops an entry whose `url` does not.

The app ships a copy taken at desktop build time. A refresh fetches `ghcr.io/modsetter/surfsense/plugins/catalog:latest`, a reference compiled into the app, and keeps it on disk. Of the bundled and the refreshed copy, the one with the later `generated_at` wins.

## How a run starts

The app spawns a process, hands it context, and waits for it to exit. The plugin does its own HTTP — to the sources it scrapes, and to the app, which already serves its API on loopback. There is no socket of ours, no message framing, and no results file.

```
<python> -m surfsense_plugin <plugin-dir> <entry> --inputs <file> --data <dir>
```

| Argument | Meaning |
|---|---|
| `<entry>` | An entry name from the manifest. The app checks this before spawn. |
| `--inputs` | A JSON object. Keys are the entry's input names, values match the declared kinds. The app writes this file. |
| `--data` | `<data>/plugins/<id>/data`. Exists from install, survives updates, deleted on uninstall. |

### Context

Everything a plugin needs to know about where it is running arrives in the environment before it starts. Nothing is discovered and nothing is negotiated. An author rarely reads these: the SDK does, so `document.add()` needs no workspace or run.

| Variable | Meaning |
|---|---|
| `SURFSENSE_PLUGIN_API_URL` | `http://127.0.0.1:<port>`. The app's own API. Every verb in the SDK is built on this. The port changes at every launch, which is why it is handed over. |
| `SURFSENSE_PLUGIN_WORKSPACE_ID` | The workspace the run was started in. Verbs default to it. |
| `SURFSENSE_PLUGIN_RUN_ID` | This run. Verbs stamp it on whatever they create. |
| `SURFSENSE_PLUGIN_ID` | The plugin's own id, so it can identify itself to the sources it calls. |
| `SURFSENSE_PLUGIN_SECRET_<NAME>` | One per declared secret. Secrets travel only here, never in a file, so they are never written to disk unencrypted. The app refuses to spawn when a declared secret has no value, or when a host in `hosts` has not been allowed. |

Nothing else of the app's reaches the plugin. The runner builds the environment from scratch: the variables above; from the operating system only `PATH`, the home and temporary directories, locale and timezone, the Windows variables Python needs (`SYSTEMROOT`, `WINDIR`, `COMSPEC`, `PATHEXT`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`), and the user's own proxy variables; and for Python `PYTHONPATH` (the SDK), `PYTHONSAFEPATH=1`, `PYTHONNOUSERSITE=1`, `PYTHONUTF8=1` and `PYTHONUNBUFFERED=1`. `PYTHONSAFEPATH` matters: `python -m` otherwise puts the working directory, which is the plugin's folder, ahead of the standard library, and a plugin's own `json.py` would replace Python's `json` for the SDK as well. Everything else is dropped. The worker's own environment holds `SURFSENSE_LOCAL_SECRET`, the key that decrypts every stored API key, and a child process inherits its parent's environment unless told otherwise. The plugin runs as the user, so this is not a wall against a hostile plugin, but the app never hands the key over.

Before it imports `main.py`, the SDK puts `<plugin-dir>` on `sys.path` and adds `<plugin-dir>/site-packages` with `site.addsitedir()`, in that order. So a plugin may split itself across files, a dependency's `.pth` file runs (pywin32 needs its own), and neither the plugin's modules nor a pinned dependency can shadow the stdlib.

### Outcome

| How it ended | Status | `error` |
|---|---|---|
| Exit 0 | `succeeded` | — |
| Any other exit | `failed` | `exit <code>` |
| Still running at the entry's `timeout_seconds` | `failed` | `timeout` |
| The app quit during the run | `failed`, set when the app next starts | `interrupted` |
| Cancelled by the user | `cancelled` | — |

Stdout and stderr are logs; the app keeps the last 16 KiB on the run and shows it, so a plugin explains a failure by writing the reason to stderr before it exits.

Stopping a plugin, for cancel or timeout, sends `SIGTERM` to it and to every process it started, then `SIGKILL` five seconds later. Whatever the plugin already committed through the API stays, because it was committed when the call returned.

A plugin is never detached from the app. It runs in the process group of the worker that started it, so quitting the app stops it and everything it started.

### Network

A plugin's HTTP goes through `http` in the SDK. Before every connection, and again on every redirect, `http` checks the host against `hosts` and raises `HostNotDeclared` naming it. It writes one line per request to the log: method, host and status, never the path or the body.

Every run start checks each host in `hosts` against the egress grants. The hosts not yet allowed come back together, and one consent prompt asks for all of them. A host revoked in Settings → Network stops the next run, not the current one.

This is a check, not enforcement. A plugin that opens its own socket or uses another HTTP client is not checked. The contributor guide asks authors to use `http`, and review asks why when a plugin does not. So the air-gapped promise is: with no host allowed, a plugin that declares hosts does not start, and a plugin that declares none never needed the network.

## The verb facade

A plugin calls `document.add(...)`. It never calls `POST /workspaces/{id}/documents`.

That indirection is the whole design. The SDK is the public contract and the routes stay internal, so a route can be renamed on a Tuesday without breaking a published plugin — we update one wrapper. The `sdk` range in a manifest is how a plugin declares which facade it was built against.

**Domains:** `workspace`, `document`, `artifact`, `model`. Complete within each. A verb missing from a domain is a gap an author routes around by calling the route directly, and a half-facade protects nothing.

v1 ships `document` alone: `add`, `list` and `update`, over routes the app already has. The other three need app routes that do not exist — nothing lets a plugin call a model, and the only artifact route generates from documents — and each lands complete, in a minor SDK version, when its routes do. A new domain is additive, so no published plugin notices.

**Not exposed:** `license`, `egress`, `migration`. No plugin has business in them.

Loopback carries no authentication, so the facade is what we sanction rather than what we prevent — a plugin can ignore the SDK and call anything. Review is the mechanism here, as it is for everything else a plugin does. The `hosts` list stays a statement about egress; loopback is not egress and does not belong in it.

## SDK surface

```python
import sys

from surfsense_plugin import document, entry, http, secret


@entry("search")
def search(query: str) -> None:
    response = http.get(
        "https://hn.algolia.com/api/v1/search",
        params={"query": query},
        headers={"Authorization": f"Bearer {secret('token')}"},
    )
    if response.status == 401:
        sys.exit("Hacker News refused your token. Update it in Settings.")
    hits = response.json()["hits"]

    seen = {existing["title"] for existing in document.list()}
    for hit in hits:
        if hit["title"] not in seen:
            document.add(title=hit["title"], content=hit["story_text"])
```

Its `plugin.json` declares what the app must know before running it:

```json
"hosts": ["hn.algolia.com"],
"secrets": [
  { "name": "token", "title": "API token", "description": "Create one in your account settings." }
],
"entries": [
  { "name": "search", "title": "Search Hacker News",
    "inputs": [{ "name": "query", "title": "Search for", "kind": "string", "required": true }] }
]
```

| In the SDK | Does |
|---|---|
| `entry` | Names a function the app can run. Its parameters are the entry's inputs, by name; an optional input the user left empty arrives as `None`. |
| `secret` | Reads a declared secret. Raises, naming it, when it is undeclared or has no value. |
| `data()` | The `--data` directory. |
| `http` | `get`, `post` and `request` on the standard library, verifying certificates against the system's certificate file. It returns a response with `status`, `headers`, `content`, `text` and `json()`, and raises on an undeclared host or a failed connection, not on a status code. |
| `document` | The facade, `workspace`, `artifact` and `model` joining it later. It reaches the app over loopback like any other HTTP call. |

Everything else is the plugin's own code: what to fetch, how to parse it, what to skip because it was done before, and migrating its own data directory after an update. No plugin code runs at install, update or uninstall, so there are no hooks for it.

A verb returns what it created, which a results file never could: an id a plugin can use in the next call.

The harness is `python -m surfsense_plugin.harness <plugin-dir> <entry> --input query=plugins`. It lays down the same files, spawns the same command, and exits with the run's code. For a plugin with dependencies it first installs `requirements.txt` into a git-ignored `site-packages/` for the author's own platform, with the flags CI uses. Verbs need the app running — see [`sdk/01-library-and-harness.md`](sdk/01-library-and-harness.md) for how it finds the port.
