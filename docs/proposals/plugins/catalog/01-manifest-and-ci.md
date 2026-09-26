# Catalog — manifest and pull-request checks

> Owns: `surfsense_local/backend/modules/plugins/manifest.py`, `plugins/RESERVED`, `.github/workflows/plugin-check.yml`.
> Contract: [`../01-protocol.md`](../01-protocol.md).

## Goal

A bad plugin folder fails in CI before anyone reviews it. The checker is a library the install path calls too, so the rules exist once.

## Work

- `load_manifest(path) -> Manifest` and `check_tree(folder, reserved: set[str]) -> list[str]`. Empty list means the folder may be merged. The strings are the review comment.
- Rules, all of them, and no others:
  - `plugin.json` matches the protocol table.
  - `id` equals the folder name and is not in `reserved` and does not start with `surfsense-`.
  - `version` is semver. When `origin/main` has the same id, the version is strictly greater.
  - `license` is `free` unless the id is reserved. A reserved id may be `free` or `paid`.
  - `requirements.txt`, if present, has every requirement pinned with `==` and no URL, no editable, no `--index-url`.
  - `main.py` exists. `LICENSE` exists. No `site-packages/` directory in the tree.
- `plugins/RESERVED` is one id per line. `example` is not reserved. Add a line when we ship a paid plugin, in the same pull request as that plugin.
- Workflow `plugin-check.yml` on pull requests that touch `plugins/**`. It runs the checker on each changed `plugins/<id>/` and fails the job with the checker's lines. It does not install requirements and it does not start Electron.
- The checker does not read imports and does not fail on a socket call.

## Acceptance

- A fixture folder that is valid produces no errors.
- One test per rule above, each with the smallest folder that breaks that rule and the error string that names it.
- A second copy of `example`'s id in another folder is an error.
- A `requirements.txt` of `requests==2.32.3` is valid. `requests>=2` is not.

## Needs from

The protocol's manifest table. Nothing from the app.
