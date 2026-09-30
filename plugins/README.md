# Plugins

A plugin adds something to SurfSense: a sidebar action that fetches, converts or writes documents into the user's workspace. Each plugin is a folder here, `plugins/<id>/`, and you add one with a pull request. It ships with the next SurfSense release, and users install it from the app.

Thank you for writing one. This guide takes you from nothing to a plugin running in your own SurfSense, then covers what to know before opening the pull request. [`example/`](example/) is a complete plugin to read alongside it: it counts the words in a text, uses a library, and remembers how many notes it has added.

## Your first plugin

Once, from the repository root, install the command every step uses:

```
uv tool install --editable plugins/core/cli
```

If your shell cannot find `surfsense-plugins` afterwards, uv printed the folder it installed into: add that folder to your `PATH`. This happens in the terminal of an editor installed as a snap. You can also skip the install and put `uv run --project plugins/core/cli` in front of every command.

Then:

| Step | Command |
|---|---|
| Start a plugin | `surfsense-plugins new hn-search` |
| Add a library it needs | `surfsense-plugins add hn-search requests` |
| Drop one it no longer needs | `surfsense-plugins remove hn-search requests` |
| Try it in your SurfSense | `surfsense-plugins invoke hn-search add-note --input text="Hello"` |

`new` lays out a plugin that runs as it is, so you can `invoke` it before changing a line. `invoke` needs SurfSense running: start it with `pnpm dev` in `surfsense_local/electron`, and `invoke` finds it on its own. The note it adds appears in your Sources.

Every command explains itself with `--help`.

## What a plugin folder holds

```
plugins/hn-search/
  manifest.json       what the app must know before it runs the plugin
  main.py             where SurfSense starts it; it imports your actions
  hn_search/          your code, in a package named after the plugin
  requirements.in     the libraries you asked for, written by add and remove
  requirements.txt    every version and file hash, never edited by hand
```

Put your code in a package named after the plugin, as `new` does. A module of your own named like a standard-library module or a library, such as `json.py`, would clash with it.

`manifest.json`:

| Field | What it is |
|---|---|
| `id` | The folder's name: lowercase letters, digits and `-` |
| `name`, `description` | What the app and the plugin directory show: up to 80 and 200 characters |
| `author` | Your name, as you want it shown |
| `access` | `free` |
| `hosts` | Every host the plugin reaches, such as `hn.algolia.com`. The user allows them before its first run. |
| `secrets` | What the user enters once in Settings, such as an API token: `name`, `title`, and an optional `description` saying where to get it |
| `actions` | What the user can run: `name`, `title`, `inputs`, and an optional `timeout_seconds`, 1800 when left out |
| `platforms` | Optional: only when the plugin cannot run on every system SurfSense supports |

An input is `{ "name", "title", "kind", "required" }`, with `kind` one of `string`, `number` or `boolean`. You never write a version: the release sets it.

## Writing the code

```python
from surfsense_plugin_sdk import action, data, document, http, secret


@action("search")
def search(query: str) -> None:
    response = http.get(
        "https://hn.algolia.com/api/v1/search",
        params={"query": query},
        headers={"Authorization": f"Bearer {secret('token')}"},
    )
    for hit in response.json()["hits"]:
        document.add(title=hit["title"], content=hit.get("story_text") or hit["title"])
```

- `@action("search")` marks the function the app runs for the action `manifest.json` names `search`.
- Inputs arrive as keyword arguments named after the declared inputs. A `string` arrives as `str`, a `number` as `int` or `float`, so annotate it `float`, and a `boolean` as `bool`. An optional input the user left empty arrives as `None`, so annotate it `str | None` or the like.
- `secret("token")` returns a secret the manifest declares, as the user entered it.
- `data()` is your plugin's own folder (see below).
- `document.add`, `list` and `update` work on the workspace the user ran the plugin in.
- When something goes wrong, say why on stderr, or with `sys.exit("Hacker News refused your token. Update it in Settings.")`. The user reads it in the run's log.

## Asking the user for things

Ask with an input for anything that changes from one run to the next, such as a search term. Ask with a secret for anything that must not be shown again, such as a token or a password. Never ask for a secret as an input: inputs are kept on the run's record.

## Network

Send every request through `http`, and list every host it reaches in `hosts`, redirects included. `http` refuses a host you did not list, and the user sees each host before the plugin's first run. A library that makes its own requests, such as a site's API client, is not checked: list every host it reaches, and say so in your pull request.

## Dependencies

Add a library with `surfsense-plugins add`, and never edit `requirements.txt` by hand: it pins every version and file hash for every system SurfSense runs on. Prefer pure-Python libraries, which ship as one small download for every system. A library with compiled code is fine if it publishes wheels for every platform in [`core/build-targets.json`](core/build-targets.json).

`invoke` installs your dependencies for your own system only, so a library missing a wheel for another system shows up in the pull request's checks, not in `invoke`.

## Your data folder

`data()` is a folder only your plugin writes to. It survives updates and goes when the plugin is uninstalled, so it is the place for what your plugin remembers between runs, such as a cache or the time it last fetched. `invoke` gives your plugin `dev-data/` beside it, which git ignores.

It is shared by every workspace. To know what is already in the workspace the user ran the plugin in, call `document.list()`.

An app can move your plugin back to an older version when a newer one is blocked, so read data a newer version wrote with care, or start over.

## Releasing

You never write a version. Once your pull request is merged, the plugin ships with the next SurfSense release, stamped with its version, and appears in the app's plugin list.

## When the SDK is missing something

You are welcome to propose it. Open the pull request beside the plugin that needs it, or an issue first; a maintainer reviews every change to the SDK, since every plugin relies on it.
