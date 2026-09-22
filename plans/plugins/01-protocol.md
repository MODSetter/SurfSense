# Protocol

The contract the SDK, the runtime, the catalog, and the app all implement. A change here is a change to every stream.

Version is `1`. The `sdk` range in a manifest is how a plugin says which version of the surface it was written against. Adding to that surface is additive. Changing or removing anything in it is a bump.

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
| `hosts` | Array of hostnames, no scheme, no path, no port. Shown in the catalog. The app does not intercept the plugin's own connections. |
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

The app spawns a process, hands it context, and waits for it to exit. The plugin does its own HTTP — to the sources it scrapes, and to the app, which already serves its API on loopback. There is no socket of ours, no message framing, and no results file.

```
<python> -m surfsense_plugin <plugin-dir> <entry> --inputs <file> --data <dir>
```

| Argument | Meaning |
|---|---|
| `<entry>` | An entry name from the manifest. The app checks this before spawn. |
| `--inputs` | A JSON object. Keys are the entry's input names, values match the declared kinds. The app writes this file. |
| `--data` | `<data>/plugins/<id>/data`. Exists from install, survives upgrades, deleted on uninstall. |

### Context

Everything a plugin needs to know about where it is running arrives in the environment before it starts. Nothing is discovered and nothing is negotiated.

| Variable | Meaning |
|---|---|
| `SURFSENSE_PLUGIN_API_URL` | `http://127.0.0.1:<port>`. The app's own API. Every verb in the SDK is built on this. |
| `SURFSENSE_PLUGIN_WORKSPACE_ID` | The workspace the run was started in. Verbs default to it. |
| `SURFSENSE_PLUGIN_RUN_ID` | This run. Verbs stamp it on whatever they create. |
| `SURFSENSE_PLUGIN_ID` | The plugin's own id, so it can identify itself to the sources it calls. |
| `SURFSENSE_PLUGIN_SECRET_<NAME>` | One per declared secret. Names match `^[a-z][a-z0-9_]{0,63}$` so they are legal variables. The app refuses to spawn when a declared secret has no stored value. |

Before it imports `main.py`, the SDK appends `<plugin-dir>` and `<plugin-dir>/site-packages` to `sys.path`, in that order. So a plugin may split itself across files, and neither its own modules nor a pinned dependency can shadow the stdlib.

### Outcome

Exit 0 is `succeeded`. Any other exit is `failed` with `error` of `exit <code>`. Stdout and stderr are logs; the app keeps the last 16 KiB on the run.

Cancel is `SIGTERM`, then `SIGKILL` five seconds later, and the run is `cancelled`. Whatever the plugin already committed through the API stays, because it was committed when the call returned.

## The verb facade

A plugin calls `document.add(...)`. It never calls `POST /workspaces/{id}/documents`.

That indirection is the whole design. The SDK is the public contract and the routes stay internal, so a route can be renamed on a Tuesday without breaking a published plugin — we update one wrapper. The `sdk` range in a manifest is how a plugin declares which facade it was built against.

**Domains:** `workspace`, `document`, `artifact`, `model`. Complete within each. A verb missing from a domain is a gap an author routes around by calling the route directly, and a half-facade protects nothing.

**Not exposed:** `license`, `egress`, `migration`. No plugin has business in them.

Loopback carries no authentication, so the facade is what we sanction rather than what we prevent — a plugin can ignore the SDK and call anything. Review is the mechanism here, as it is for everything else a plugin does. The `hosts` list stays a statement about egress; loopback is not egress and does not belong in it.

## SDK surface

```python
import json
import urllib.request

from surfsense_plugin import document, entry, secret


@entry("search")
def search(query: str) -> None:
    token = secret("token")
    request = urllib.request.Request(
        f"https://hn.algolia.com/api/v1/search?query={query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request) as response:
        hits = json.load(response)["hits"]

    seen = {existing["title"] for existing in document.list()}
    for hit in hits:
        if hit["title"] not in seen:
            document.add(title=hit["title"], content=hit["story_text"])
```

`entry` names a function the app can run. `secret` reads its variable and raises when it is absent. `data()` returns the `--data` directory. The rest is the facade, and it reaches the app over loopback like any other HTTP call.

A verb returns what it created, which is what the file never could: an id a plugin can use in the next call.

The harness is `python -m surfsense_plugin.harness <plugin-dir> <entry> --input query=plugins`. It lays down the same files, spawns the same command, and exits with the run's code. Verbs need the app running — see [`sdk/01-library-and-harness.md`](sdk/01-library-and-harness.md) for how it finds the port.
