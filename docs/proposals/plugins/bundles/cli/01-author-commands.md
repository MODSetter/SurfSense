# CLI — author commands

> Owns: `plugins/bundles/core/cli/`, the project behind the `surfsense-plugins` command, and its author commands `new`, `add`, `remove`, `pin-dependencies` and `invoke`; `plugins/bundles/example/`; `plugins/README.md`; the `dev-data/` line in `plugins/.gitignore`.
> Contract: [`../01-protocol.md`](../01-protocol.md). Uses: the SDK ([`../sdk/01-library.md`](../sdk/01-library.md)), the manifest rules, and packaging's install step ([`../release/01-packaging.md`](../release/01-packaging.md)).

## Goal

An author goes from nothing to a plugin running in their own SurfSense in a few commands, and runs exactly what CI runs before opening a pull request. Contributing should be pleasant: every step of the journey is one verb, every error says what to do next, and nobody copies a long command out of a doc.

## The author's journey

| Step | Command | What it does |
|---|---|---|
| Start | `surfsense-plugins new hn-search` | Lays out `plugins/hn-search/` from a template that passes the manifest rules and runs as it is |
| Add a library | `surfsense-plugins add hn-search lxml` | Adds the line to `requirements.in` and pins `requirements.txt` for every platform, with hashes |
| Drop a library | `surfsense-plugins remove hn-search lxml` | Removes it from both files |
| Re-pin | `surfsense-plugins pin-dependencies hn-search` | Pins again after a hand edit of `requirements.in`, or when `build-targets.json` gains a platform |
| Try it | `surfsense-plugins invoke hn-search search --input query=plugins` | Runs the action once against the author's running SurfSense; its note appears in Sources |
| Before the pull request | `surfsense-plugins check hn-search` | Exactly what CI runs ([`../release/02-pull-request-checks.md`](../release/02-pull-request-checks.md)) |

## Work

- `plugins/bundles/core/cli/pyproject.toml`: the package `surfsense_plugin_cli`, and the command `surfsense-plugins` through `[project.scripts]`, built with Typer. Its Python is pinned to the version in `plugins/bundles/core/build-targets.json`, because `invoke` runs plugins on it. It depends on the manifest rules by path, and on the `uv` package, so every machine pins and installs with the same `uv`.
- One folder per job in the package: `new/`, `dependencies/` for `add`, `remove` and `pin-dependencies`, `invoke/`, and later `packaging/`, `check/`, `audit/`, `release/` and `directory_site/`. What several jobs share sits beside them: `plugin_folder.py` finds a plugin's folder and loads its manifest through the rules, and `build_targets.py` reads `build-targets.json`.
- Output a person can act on. Every command says what it did, so a success is never silent. An error says what to do next and never shows a traceback. Colours when a person reads the terminal, plain text when a machine does. Every command's `--help` shows an example.
- `new <id>` refuses an id that breaks the id rule, is taken, or is reserved, and says which. Otherwise it lays down `plugins/<id>/`: a `manifest.json` with the id, a name and description to edit, `author` from `git config user.name`, `access: free`, `hosts: []` and one action with one text input; a `main.py` that imports the action from a package named after the plugin, such as `hn_search/`. The result runs with `invoke` unchanged.
- `add <plugin> <requirement>…` and `remove <plugin> <name>…` edit `requirements.in`, which stays the short list of what the plugin asked for and reads well in review. All three dependency commands then pin through one function, running the protocol's `uv pip compile` command, and keep the versions already pinned, so adding one library upgrades nothing else.
- `invoke <plugin> <action> [--input name=value]… [--workspace id] [--api-url url]`:
  - Loads the manifest through the rules, and refuses an action it does not declare.
  - Converts each `--input` to its declared kind: a `number` to `int` or `float`, a `boolean` from `true` or `false`. It refuses an unknown name, a value of the wrong kind, and a missing required input, as the app's run route does.
  - Finds the app at `--api-url`, else `SURFSENSE_PLUGIN_API_URL`, else `~/.surfsense-dev/api-url`, which a development app writes, else `~/.surfsense/api-url`, which a packaged app writes. When none answers: "SurfSense is not running: start it, or pass --api-url".
  - Writes to `--workspace`. Without it, to the app's only workspace; with several, or with an id the app does not have, it lists their ids and names and runs nothing.
  - Takes each declared secret from the author's own `SURFSENSE_PLUGIN_SECRET_<NAME>`, else from a hidden prompt, never from a flag, so secrets stay out of shell history.
  - Installs `requirements.txt` into `plugins/<id>/site-packages/` for this machine's platform through packaging's install step, `install_requirements(plugin, platform, into)`, so an author's machine installs what a release installs. It skips the install when `requirements.txt` has not changed since the last one. A dependency with no prebuilt wheel for this platform fails, naming the package and the platform.
  - Gives the plugin `plugins/<id>/dev-data/` as its data folder: git-ignored, kept between invokes, and never mixed with a copy installed in the app.
  - Says on stderr which action runs, in which workspace and at which address, then `Done.` or `Failed: exit <code>.`, so the plugin's own output stays the command's only output.
  - Runs `python -S -m surfsense_plugin_sdk.run` on the CLI's own Python, blind to the CLI's packages, with the environment the app's runner builds, streams the plugin's log to the terminal, and exits with its code. It sets no run id, so a note's provenance names no run. It does not intercept HTTP and does not stub the app.
  - Runs outside the app, so the app's egress consent does not apply. The SDK's `http` still refuses a host the manifest does not declare.
- `plugins/bundles/example/`, a word counter. `access: free`, `hosts: []`, no secrets. One action, `count-words`, with a required string input `text` and an optional number input `top`, 10 when empty. It depends on `tabulate`, which is pure Python, so it packages into one `any` file. It adds a note titled "Word count #N" holding the text and a table of its `top` most frequent words, and counts N in `data()`. Its `main.py` imports only the SDK and its own package. The other streams' tests run it, and the guide points at it rather than pasting a second copy. It is not a product plugin.
- `plugins/README.md` is the contributor guide. It opens with the journey above, then covers:
  - the folder layout and every `manifest.json` field, including `platforms` and `timeout_seconds`. Beyond a small `main.py`, put the code in a package named after the plugin, such as `hn_search/`, so no file of yours can clash with a standard-library module or a dependency;
  - what to ask the user and where: an input when it changes every run, a secret for anything that must not be shown again. Never ask for a secret as an input;
  - how inputs arrive: as keyword arguments named after the declared inputs, a `string` as `str`, a `number` as `int` or `float`, so annotate it `float`, a `boolean` as `bool`, and an optional input the user left empty as `None`, so annotate it `str | None` or the like;
  - the accessors, `http`, and the verbs, and that a failure is explained by writing the reason to stderr, which the user sees in the run's log;
  - that a plugin needing something the SDK lacks is welcome to propose it, as [`../02-extending.md`](../02-extending.md#growing-the-sdk-together) describes;
  - network: send every request through `http` and list every host it reaches, redirects included. Another client (`requests`, a browser) is not checked; say why in the pull request;
  - dependencies: add them with `add`, never edit `requirements.txt` by hand. Prefer pure-Python packages, which ship as one small download for every system. A compiled one is fine if it publishes wheels for every platform in `plugins/bundles/core/build-targets.json`. `invoke` installs for your own platform only, so a library missing a wheel for another system shows up in `check`, not in `invoke`;
  - releasing: you never write a version. A merged change ships with the next SurfSense release, stamped with its version, and the directory site shows it once that release is published ([`../04-versioning.md`](../04-versioning.md));
  - the data directory survives updates, and an app can move a plugin back to an older version when a newer one is blocked, so read data written by a newer version carefully, or start over. It is also shared by every workspace: to know what is already in the run's workspace, call `document.list()`, and keep in the data directory what belongs to the plugin itself, such as a cache or the time it last fetched.
- A `check-cli` job in `plugins-pull-request-checks.yml`, beside `check-sdk`.

## Later

- `check`, with packaging ([`../release/01-packaging.md`](../release/01-packaging.md), [`../release/02-pull-request-checks.md`](../release/02-pull-request-checks.md)). With `--output-format github`, a failing rule prints GitHub's `::error file=…,line=…::` line, so it appears on that line of the pull request's diff.
- A testing kit: the SDK's stub app as a pytest fixture, so a plugin can ship offline tests in its `tests/` and run them with `surfsense-plugins test`.
- `dev`: watches the plugin and invokes it again on every save. The name is kept for it; `invoke` runs once.

## Acceptance

- `new hn-search` creates a folder that passes the manifest rules and that `invoke` runs unchanged. `new` with a taken, reserved or badly formed id changes nothing and says why.
- `add example tabulate` adds the line to `requirements.in` and pins `requirements.txt` with hashes. A second `add` keeps the first library's pinned version. `remove` drops a library from both files.
- `invoke example count-words --input text="a b a"` against a running app exits 0, and a note titled "Word count #1" with the table is in the workspace. A second invoke adds "Word count #2".
- A second invoke with an unchanged `requirements.txt` installs nothing.
- With two workspaces and no `--workspace`, `invoke` lists both and runs nothing.
- With no app running, `invoke` says so and names `--api-url`.
- `--input top=many` fails naming `top` and its kind. An undeclared input fails naming it, and so does a missing required one.
- A declared secret with no variable set is asked for with a hidden prompt, and appears in no file.
- A dependency with no wheel for this platform fails naming the package and the platform.

## Testing

The commands run as subprocesses against a stub app, the pattern the SDK's tests use. Pinning and installing run against a folder of wheels the test builds, with `--no-index`, so no test needs PyPI. One acceptance run uses the example against a real app.

## Needs from

The SDK and the manifest rules, both merged. `plugins/bundles/core/build-targets.json`, which this stream adds if it lands before packaging. Packaging's install step, which this stream writes first and packaging reuses. Electron's `api-url` file ([`../app/01-api.md`](../app/01-api.md)); until it lands, `--api-url` finds the app.
