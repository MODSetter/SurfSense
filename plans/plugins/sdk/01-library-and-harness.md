# SDK — library and harness

> Owns: `plugins/sdk/`, `plugins/example/`, `plugins/README.md`.
> Contract: [`../01-protocol.md`](../01-protocol.md).

## Goal

An author runs a plugin on her machine, against the real protocol, without Electron and without the frozen app.

## Work

- Package `surfsense_plugin` in `plugins/sdk/`. `__main__` reads the arguments from the protocol, calls the matching `@entry` function, and exits 0 or 1. `entry`, `result`, and `secret` are the whole public surface. There is no `fetch`. No other module is imported by `plugins/example`.
- `secret` reads `SURFSENSE_PLUGIN_SECRET_<NAME>`. `result` appends one JSON line to the results file and flushes it.
- `python -m surfsense_plugin.harness` as specified. It does not intercept HTTP. `SURFSENSE_PLUGIN_SECRET_<NAME>` supplies a secret.
- `plugins/example/`. `license: free`, `hosts: []`, one entry `echo` with a string input `text`, no requirements. The entry sends one `document` result whose content is the input. This is the plugin the other streams' tests run. It is not a product plugin.
- `plugins/README.md` is the contributor guide: the folder layout, `plugin.json` fields, the four functions, the harness command, how a pull request is checked, and the fact that `requirements.txt` is installed by CI rather than on the user's machine. Point at `plugins/example` instead of pasting a second copy of it.

## Acceptance

- `python -m surfsense_plugin.harness plugins/example echo --input text=hi` prints one JSON line with `kind` `document` and content `hi`, and exits 0.
- A plugin whose entry raises exits non-zero and leaves any results lines it flushed before the exception.
- A unit test calls `result` twice and reads two JSON lines back, and calls `secret` with the variable set and with it missing.
- The example plugin's `main.py` imports only `surfsense_plugin`.

## Needs from

Nothing in the app. The runtime stream consumes this package later by spawning `python -m surfsense_plugin`. Until [`../python/01-interpreter.md`](../python/01-interpreter.md) lands, `python` is `uv run` from `plugins/sdk`.
