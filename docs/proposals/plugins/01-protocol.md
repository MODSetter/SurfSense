# Protocol

The contract the SDK, the runtime, the catalog, and the app all implement. A change here is a change to every stream.

Version is `1`. The handshake and `sdk` range are how a later version shows up. Do not add a field to a message without bumping it.

## On disk

```
plugins/<id>/
  plugin.json
  main.py
  requirements.txt    # omitted when there are no dependencies
  README.md
  LICENSE
  tests/              # optional
  fixtures/           # optional
```

`site-packages/` is not in git. CI creates it inside the tarball.

### `plugin.json`

| Field | Rule |
|---|---|
| `id` | Equals the folder name. Pattern above. |
| `name` | Display string, 1–80 characters. |
| `author` | Display string. Not unique. |
| `version` | Semver `MAJOR.MINOR.PATCH`. |
| `sdk` | A PEP 440 specifier. The app's SDK version must satisfy it or the run does not start. |
| `license` | `free` or `paid`. |
| `hosts` | Array of hostnames, no scheme, no path, no port. Shown in the catalog. Each one needs the user's consent before the plugin's first run. The app does not intercept the plugin's own connections. |
| `secrets` | Array of names. Values are never in this file. |
| `entries` | At least one. |

An entry:

| Field | Rule |
|---|---|
| `name` | `^[a-z][a-z0-9-]{0,63}$`, unique within the plugin. |
| `title` | Display string. |
| `inputs` | Array, may be empty. Each is `{ "name", "kind", "required" }`. `kind` is `string`, `number`, or `boolean`. |

Unknown fields are ignored, so a future field does not break an older app. A missing required field, a bad id, or a second entry with the same name fails the manifest check.

### Tarball

`<id>-<version>.tar.gz`. One top-level directory `<id>-<version>/` containing the folder above plus `site-packages/` when CI installed dependencies. The `plugin.json` inside the tarball must deep-equal the catalog entry's manifest fields (`id`, `name`, `author`, `version`, `sdk`, `license`, `hosts`, `secrets`, `entries`). A mismatch rejects the install. The sha256 is of the gzip bytes.

Extraction rejects any member whose path is absolute, contains `..`, or is a link that resolves outside the destination. The destination is `<data>/plugins/<id>/<version>.tmp-<pid>/`, then one rename to `<data>/plugins/<id>/<version>/`.

### Catalog

One JSON file, `catalog.json`:

```json
{
  "plugins": [
    {
      "id": "example",
      "name": "Example",
      "author": "SurfSense",
      "version": "1.0.0",
      "sdk": ">=1,<2",
      "license": "free",
      "hosts": [],
      "secrets": [],
      "entries": [],
      "url": "https://github.com/MODSetter/SurfSense/releases/download/plugin-example-1.0.0/example-1.0.0.tar.gz",
      "sha256": "<64 hex>",
      "yanked": false
    }
  ]
}
```

The app ships a copy taken at desktop build time. A refresh downloads this same file from a URL compiled into the app, and only from that URL. `yanked: true` stays in the file so an already-installed copy can be refused with a reason.

## How a run starts

There is no socket and no request protocol. The plugin does its own network calls, reads secrets from the environment, and appends results to a file. The app spawns it and reads that file after the process exits.

```
<python> -m surfsense_plugin <plugin-dir> <entry> --inputs <file> --results <file> --data <dir>
```

| Argument | Meaning |
|---|---|
| `<entry>` | An entry name from the manifest. The app checks this before spawn. |
| `--inputs` | A JSON object. Keys are the entry's input names, values match the declared kinds. The app writes this file. |
| `--results` | An empty file the app creates. The plugin appends one JSON object per line. |
| `--data` | `<data>/plugins/<id>/data`. Exists from install, survives upgrades, deleted on uninstall. |

For each secret name in the manifest, the app sets `SURFSENSE_PLUGIN_SECRET_<NAME>` to the stored value. Secret names match `^[a-z][a-z0-9_]{0,63}$` so they are environment variables. The app refuses to spawn when a declared secret has no stored value, or when a host in `hosts` has not been allowed.

Stdout and stderr are logs. The app keeps the last 16 KiB on the run.

Exit 0 is success. Any other exit is `failed`. The app still imports every well-formed results line already in the file.

Cancel: `SIGTERM`, then `SIGKILL` five seconds later. The run is `cancelled`. Lines already flushed stay.

### Results file

Each line is one JSON object, flushed before the next one:

```json
{"kind":"document","body":{"title":"Show HN","content":"..."}}
```

| `kind` | `body` | What the app does after the process exits |
|---|---|---|
| `document` | `{ "title": str, "content": str }` | Insert a `NOTE` in the run's workspace, set `document_metadata` to `{ "pluginId", "entry", "runId" }`, enqueue `ingest_document`. Do not set `dedup_key`. |
| anything else | a JSON object | Insert a row on the run: `kind` + `body`. The screen shows it. |

A line over 1 MiB, or a line that is not JSON, is skipped. The valid lines before and after it are still imported. A run that writes no lines is a success that produced nothing. `document` is how a source plugin puts something in the library. It is not required.

The plugin's own HTTP is ordinary Python. The app does not see those calls. Every run start checks each host in `hosts` against the egress grants, and a host not yet allowed raises the egress consent prompt, so consent is asked before the first run and a host revoked in Settings → Network stops the next one. Nothing checks the plugin's calls during a run, so the app cannot stop a call to a host the plugin did not declare. `hosts` is also what the catalog shows.

## SDK surface

```python
import urllib.request
from surfsense_plugin import entry, result, secret

@entry("search")
def search(query: str) -> None:
    token = secret("token")
    request = urllib.request.Request(
        "https://hacker-news.firebaseio.com/v0/item/1.json",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request) as response:
        body = response.read().decode()
    result("document", {"title": "Show HN", "content": body})
```

`secret` reads the environment variable. A missing one raises. `result` appends one line to the results file and flushes it. There is no `fetch` in the SDK.

The harness is `python -m surfsense_plugin.harness <plugin-dir> <entry> --input query=plugins`. It passes secrets from the process environment, runs the entry, and prints the results file. It does not intercept HTTP.
