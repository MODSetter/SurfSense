# Protocol

The contract the SDK, the runtime, the release tooling, and the app all implement. A change here is a change to every stream.

The protocol has no version of its own. It changes only with an app release, and a plugin stamped with version X speaks the protocol of SurfSense X ([`04-versioning.md`](04-versioning.md)). Adding to the surface is additive; changing or removing anything in it breaks the plugins that use it, which the checks refuse until those plugins are updated in the same pull request ([`02-extending.md`](02-extending.md)).

## On disk

```
plugins/
  core/                          everything maintainers own, under one CODEOWNERS line
    sdk/                         the SDK, shipped inside the app; its own project, with no dependencies
    manifest/                    the manifest rules, used by the checks and by the app at install
    cli/                         the `surfsense-plugins` command: author commands, packaging, checks, releases, the directory site
    build-targets.json           the Python version and platforms plugins are built for
    policy/
      reserved-plugin-ids.txt
      withdrawn-versions.txt
      size-limit-exceptions.txt
  README.md                      the contributor guide
  <id>/                          one folder per plugin; nothing else sits beside core/
```

`plugins/core/cli/` is one Python project with one command, `surfsense-plugins`, and a subcommand per job. For authors: `new`, `add`, `remove`, `pin-dependencies`, `invoke` and `check`. For CI and maintainers: `audit`, `plan`, `upload`, `go-live`, `withdraw` and `build-directory-site`. Each job is a folder in its package, `surfsense_plugin_cli` ([`cli/01-author-commands.md`](cli/01-author-commands.md)). Workflows only call it, so every step also runs on a maintainer's machine.

A plugin's folder:

```
plugins/<id>/
  manifest.json
  main.py             where the SDK starts; it imports the rest
  <package>/          optional: the plugin's own code, split as it likes
  requirements.in     omitted when there are no dependencies
  requirements.txt    generated from requirements.in, never edited by hand
  README.md           optional: for readers on GitHub; the app shows `description`
  tests/              optional
  fixtures/           optional
```

A plugin carries no license of its own. Like everything outside `surfsense_backend/app/proprietary/`, it is Apache-2.0 under the repository's [`LICENSE`](../../../LICENSE), and a pull request's contribution is Apache-2.0 by section 5 of that license. `access` is a different thing: whether running the plugin needs a SurfSense license file.

`main.py` is only the entry point. A plugin may be any number of modules and packages, and any data files it reads; the packaged file carries the whole folder. The SDK imports `main.py`, so an `@action` function defined elsewhere must be imported from it. A top-level module named like a standard-library module or a dependency fails the checks, because the path order would ignore it or let it hide the library; code in a package named after the plugin never clashes.

`site-packages/` is never in git. Packaging creates it inside each downloadable file, and `surfsense-plugins invoke` creates a git-ignored one on the author's machine, beside the git-ignored `dev-data/` it gives the plugin as its data folder.

### Dependencies

`requirements.in` names what the plugin imports. `requirements.txt` is generated from it, and it is what pins. `surfsense-plugins add`, `remove` and `pin-dependencies` write both, pinning with:

```
uv pip compile --universal --generate-hashes --python-version 3.12 requirements.in -o requirements.txt
```

It pins every transitive dependency for every platform, with a sha256 per file, so the files packaging installs are the files review saw. PyPI only, prebuilt wheels only: no URLs, no editable installs, no index options, and no source distributions, because a Linux runner cannot compile one for Windows or macOS.

### `manifest.json`

| Field | Rule |
|---|---|
| `id` | Equals the folder name. `^[a-z][a-z0-9-]{0,63}$`. Once published, taken for good: a removed plugin's id is never given to another folder, or its installed copies would update to someone else's code. |
| `name` | Display string, 1–80 characters. |
| `description` | One line for the plugin list and the directory site, 1–200 characters. |
| `author` | Display string. Not unique. |
| `access` | `free` or `paid`. Only a reserved id may be `paid`. |
| `hosts` | Array of exact hostnames: no scheme, path, port or wildcard, and never a loopback name. Shown in the app and on the directory site. Each one needs the user's consent before the plugin's first run, and the SDK's `http` refuses any host not listed. |
| `secrets` | Optional array of what the user enters once, in Settings, stored encrypted and never shown again: an API token, a password. Each is `{ "name", "title", "description" }`: `name` matches `^[a-z][a-z0-9_]{0,63}$` so it is a legal variable name, `title` is the label, and the optional `description` says where to get it. Every declared secret is required. Values are never in this file. |
| `platforms` | Optional. A non-empty subset of the platform keys in `plugins/core/build-targets.json`. Absent means all of them. On any other system the app does not list the plugin. |
| `actions` | At least one. |

An author writes no `version` and no compatibility field: the release stamps the version into the packaged copy of this file, where the app reads it, and compatibility follows from it ([`04-versioning.md`](04-versioning.md)). A `version` written in the repository is replaced.

An action:

| Field | Rule |
|---|---|
| `name` | `^[a-z][a-z0-9-]{0,63}$`, unique within the plugin. |
| `title` | Display string. |
| `inputs` | Array, may be empty. The run dialog asks for them every run. Each is `{ "name", "title", "kind", "required" }`: `name` matches `^[a-z][a-z0-9_]{0,63}$` and is unique within the action, `title` is the label, `kind` is `string`, `number`, or `boolean`, and `required` defaults to `false`. |
| `timeout_seconds` | Optional integer, 1 to 21600. Absent means 1800. A run still going at that point is stopped and fails. |

Every name is checked twice: its shape on its own, and that no other item in its list uses it.

| Name | Shape | Unique within | Because it becomes |
|---|---|---|---|
| `id` | `^[a-z][a-z0-9-]{0,63}$` | every plugin, as the folder's name | a folder, file and URL name |
| action `name` | `^[a-z][a-z0-9-]{0,63}$` | the plugin's actions | how the app picks the function to run, and part of the run's URL |
| input `name` | `^[a-z][a-z0-9_]{0,63}$` | the action's inputs | a Python keyword argument |
| secret `name` | `^[a-z][a-z0-9_]{0,63}$` | the plugin's secrets | `SURFSENSE_PLUGIN_SECRET_<NAME>` |

Unknown fields are ignored. A missing required field, a badly shaped name, or a name used twice in its list fails the checks.

### What the user provides

| The user provides | Asked | Kept | The plugin reads it with |
|---|---|---|---|
| An input | every run, in the run dialog | on the run's record | the action function's arguments |
| A secret | once, in Settings, never shown again | encrypted through `shared/secrets.py` | `secret("name")` |

The app draws both forms from these declarations; a plugin never draws its own. Until every secret has a value, the plugin's sidebar actions are replaced by a "Set up" action.

More kinds of input, and settings that are not secret, come the way any capability does: with the first plugin that needs them ([`02-extending.md`](02-extending.md#growing-the-sdk-together)).

### Build targets

`plugins/core/build-targets.json` is the one list of what plugins are built for: the CPython version the app ships, and each platform with the `uv` target that picks wheels old enough for the app's oldest supported systems, Ubuntu 22.04, RHEL 9 and macOS 13.3 ([packaging](../../architecture/packaging.md)).

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

The interpreter fetch script, packaging and the checks all read it. There is no Intel Mac target ([ADR 0021](../../adr/0021-no-intel-mac-build.md)).

### Downloadable files

A download key is `any`, or `cp<major><minor>-<platform>` such as `cp312-linux-x64`, because compiled code runs only on the platform and the Python it was built for. Packaging builds one `any` file when the dependencies install to the same files on every target in `platforms`, and one file per target otherwise ([`release/01-packaging.md`](release/01-packaging.md)).

`<id>-<version>-<key>.tar.gz`, for example `pdf-tools-2.4.0-cp312-linux-x64.tar.gz`. One top-level directory, `<id>-<version>/`, holding the files of the plugin's folder, not the folder itself, plus `site-packages/` when there are dependencies. Its `manifest.json` is the repository's with the stamped `version` added, and it replaces the original. That `manifest.json`, less `id` and `version`, must deep-equal the catalog version's `manifest`, and its `id` and `version` must equal the catalog's. A mismatch rejects the install. The sha256 is of the gzip bytes. A file is at most 100 MB unless `plugins/core/policy/size-limit-exceptions.txt` names the plugin.

A published version never changes. Uploading a version that already exists with different bytes fails.

Extraction strips the top-level directory and rejects any member whose path is absolute, contains `..`, or is a link that resolves outside the destination. The destination is `<data>/plugins/<id>/<version>.tmp-<pid>/`, then one rename to `<data>/plugins/<id>/<version>/`. One version stays on disk: once a new one is in place, the previous directory is deleted.

### Catalog

One JSON file, `plugin-catalog.json`:

```json
{
  "schema_version": 1,
  "released_with": "2.4.0",
  "generated_at": "2026-10-05T12:00:00Z",
  "plugins": [
    {
      "id": "hn-search",
      "versions": [
        {
          "version": "2.4.0",
          "manifest": {
            "name": "Hacker News search",
            "description": "Adds matching stories as notes.",
            "author": "Alice",
            "access": "free",
            "hosts": ["hn.algolia.com"],
            "secrets": [{ "name": "token", "title": "API token" }],
            "actions": [
              {
                "name": "search",
                "title": "Search Hacker News",
                "inputs": [{ "name": "query", "title": "Search for", "kind": "string", "required": true }]
              }
            ]
          },
          "downloads": {
            "any": {
              "url": "https://github.com/SurfSense-Inc/surfsense-plugin-releases/releases/download/surfsense-2.4.0/hn-search-2.4.0-any.tar.gz",
              "sha256": "<64 hex>",
              "size": 412345
            }
          },
          "blocked": [{ "reason": "Deletes notes by mistake.", "source": "maintainer" }]
        },
        { "version": "2.3.0", "manifest": { "…": "…" }, "downloads": { "…": "…" } }
      ]
    }
  ]
}
```

- **Every published version stays**, newest first, each with its own `manifest`, since hosts, secrets and actions may differ between versions. How an app picks among them, and what `blocked` means, is in [`04-versioning.md`](04-versioning.md).
- `blocked` is a list, empty or absent when the version is not blocked; [`04-versioning.md`](04-versioning.md#stopping-a-version-blocked) says how entries are written and combined.
- `released_with` is the app release whose run produced the file; a catalog republished by `withdraw` keeps it. `generated_at` is when it was written.
- `schema_version` is raised only when the structure breaks; adding an optional field does not raise it. An app that does not know a catalog's `schema_version` ignores that file and keeps the copy it has. Should it ever be raised, the old format keeps being published beside the new one for older apps.
- A plugin whose folder was removed gets `"removed_from_app": "<version>"`, and apps from that version on no longer list it.
- Every `url` starts with `https://github.com/SurfSense-Inc/surfsense-plugin-releases/releases/download/`. The app drops a version whose `url` does not.

The app ships the catalog of its own release. A refresh fetches the live one from `https://github.com/SurfSense-Inc/surfsense-plugin-releases/releases/latest/download/plugin-catalog.json`, a URL compiled into the app, and keeps it on disk. Of the bundled and the refreshed copy, the one with the higher `released_with` wins, and between equal ones the later `generated_at`. Comparing releases first matters: a withdrawal published while release N is still a draft is written later than N's bundled catalog, but from release N−1's, and must not replace it on app N.

### Where versions are published

Published files live in a second public repository, `SurfSense-Inc/surfsense-plugin-releases`, as GitHub Releases. This repository's own releases are the app's update channel and must hold nothing else. A public repository's releases are public once published, with no setting to change, GitHub reports a download count per file, and the app downloads them over plain HTTPS.

```
SurfSense-Inc/surfsense-plugin-releases
  release "surfsense-2.4.0"               the plugins published with SurfSense 2.4.0
    hn-search-2.4.0-any.tar.gz
    pdf-tools-2.4.0-cp312-linux-x64.tar.gz
    pdf-tools-2.4.0-cp312-macos-arm64.tar.gz
    pdf-tools-2.4.0-cp312-windows-x64.tar.gz
    plugin-catalog.json
  release "withdrawal-20261005T120000Z"   a catalog republished by withdraw, and nothing else
    plugin-catalog.json
  branch "gh-pages"                       the directory site
```

The newest published release is marked latest, so its `plugin-catalog.json` is the live one, and every earlier catalog stays readable in its own release. Nothing in that repository is edited by hand; [`release/03-publishing.md`](release/03-publishing.md) writes it.

## How a run starts

The app spawns a process, hands it context, and waits for it to exit. The plugin does its own HTTP — to the sources it scrapes, and to the app, which already serves its API on loopback. There is no socket of ours, no message framing, and no results file.

```
<python> -m surfsense_plugin_sdk.run <plugin-dir> <action> --inputs <file> --data <dir>
```

| Argument | Meaning |
|---|---|
| `<action>` | An action name from the manifest. The app checks this before spawn. |
| `--inputs` | A JSON object. Keys are the action's input names, values match the declared kinds. The app writes this file. |
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
| Still running at the action's `timeout_seconds` | `failed` | `timeout` |
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

That indirection is the whole design. The SDK is the public contract and the routes stay internal, so a route can be renamed on a Tuesday without breaking a published plugin — we update one wrapper, and the contract tests prove it ([`sdk/01-library.md`](sdk/01-library.md)).

**Domains:** `workspace`, `document`, `artifact`, `model`. Complete within each. A verb missing from a domain is a gap an author routes around by calling the route directly, and a half-facade protects nothing.

v1 ships `document` alone: `add`, `list` and `update`, over routes the app already has. The other three need app routes that do not exist — nothing lets a plugin call a model, and the only artifact route generates from documents — and each lands complete, with an app release, when its routes do. A new domain is additive, so no published plugin notices.

**Not exposed:** `license`, `egress`, `migration`. No plugin has business in them.

Loopback carries no authentication, so the facade is what we sanction rather than what we prevent — a plugin can ignore the SDK and call anything. Review is the mechanism here, as it is for everything else a plugin does. The `hosts` list stays a statement about egress; loopback is not egress and does not belong in it.

## SDK surface

```python
import sys

from surfsense_plugin_sdk import action, document, http, secret


@action("search")
def search(query: str) -> None:
    response = http.get(
        "https://hn.algolia.com/api/v1/search",
        params={"query": query},
        headers={"Authorization": f"Bearer {secret('token')}"},
    )
    if response.status == 401:
        sys.exit("Hacker News refused your token. Update it in Settings.")
    hits = response.json()["hits"]

    seen = {existing.title for existing in document.list()}
    for hit in hits:
        if hit["title"] not in seen:
            document.add(title=hit["title"], content=hit["story_text"])
```

Its `manifest.json` declares what the app must know before running it:

```json
"hosts": ["hn.algolia.com"],
"secrets": [
  { "name": "token", "title": "API token", "description": "Create one in your account settings." }
],
"actions": [
  { "name": "search", "title": "Search Hacker News",
    "inputs": [{ "name": "query", "title": "Search for", "kind": "string", "required": true }] }
]
```

| In the SDK | Does |
|---|---|
| `action` | Names a function the app can run. Its parameters are the action's inputs, by name; an optional input the user left empty arrives as `None`. |
| `secret` | Reads a declared secret. Raises, naming it, when it is undeclared or has no value. |
| `data()` | The `--data` directory. |
| `http` | `get`, `post` and `request` on the standard library, verifying certificates against the system's certificate file. It returns a response with `status`, `headers`, `content`, `text` and `json()`, and raises on an undeclared host or a failed connection, not on a status code. |
| `document` | The facade, `workspace`, `artifact` and `model` joining it later. It reaches the app over loopback like any other HTTP call, and returns typed objects: `document.add()` returns a `Document`. |

Everything the SDK exposes is typed, with no `Any` except `Response.json()`, whose shape comes from the source, so the checks can type-check every plugin against it ([`release/02-pull-request-checks.md`](release/02-pull-request-checks.md)). Everything else is the plugin's own code: what to fetch, how to parse it, what to skip because it was done before, and migrating its own data directory after an update. No plugin code runs at install, update or uninstall, so there are no hooks for it.

A verb returns what it created, which a results file never could: an id a plugin can use in the next call.

An author runs a plugin with `surfsense-plugins invoke <plugin> <action> --input query=plugins`. It installs the plugin's dependencies for the author's own platform the way packaging does, spawns the same command the app does, and exits with the run's code. Verbs need the app running — see [`cli/01-author-commands.md`](cli/01-author-commands.md) for how it finds it.
