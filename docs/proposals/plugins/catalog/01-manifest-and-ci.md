# Catalog — manifest and pull-request checks

> Owns: `surfsense_local/backend/modules/plugins/manifest.py`, `plugins/core/build/`, `plugins/core/targets.json`, `plugins/core/RESERVED`, `plugins/core/SIZE-EXCEPTIONS`, `.github/workflows/plugin-check.yml`, the plugin lines in `.github/CODEOWNERS`.
> Contract: [`../01-protocol.md`](../01-protocol.md).

## Goal

A bad plugin folder fails in CI before anyone reviews it, with a message its author can act on, and the author can run the same checks first. The manifest rules are a library the install path calls too, so they exist once.

## Work

- `load_manifest(path) -> Manifest` and `check_tree(folder, base_version, reserved, allow_reserved) -> list[str]`. Empty list means the folder may be merged. The strings are the review comment.
- Tree rules, all of them, and no others:
  - `plugin.json` matches the protocol tables, including `platforms` against `plugins/core/targets.json` and `timeout_seconds` within its range. A host with a scheme, port, path or wildcard, or a loopback name, is an error.
  - Every input has a legal, unique name, a `title`, and a `kind` of `string`, `number` or `boolean`. Every secret has a legal, unique name and a `title`.
  - `id` equals the folder name.
  - An id listed in `plugins/core/RESERVED`, or starting with `surfsense-`, passes only with `allow_reserved`. `access: paid` passes only on such an id.
  - `version` is semver. When anything under the folder changed, it is strictly greater than on the pull request's base branch, so a published version never changes.
  - `requirements.in` and `requirements.txt` are both present or both absent. Every requirement in `requirements.txt` is pinned with `==` and carries a `--hash`. No URL, no editable install, no `--index-url`, `--extra-index-url` or `--find-links`.
  - `main.py` exists. No `LICENSE` or other license file of the plugin's own: plugins are Apache-2.0 under the repository's license. No `site-packages/` in git.
  - No top-level module or package in the folder is named like a standard-library module (`sys.stdlib_module_names`) or `surfsense_plugin`. The standard library comes first on the path, so such a file would be silently ignored. The line names the clash and suggests a package named after the plugin.
- Build rules, run by `plugins/core/build/`, the same tool publishing uses, here without uploading. A folder, one file per step:
  - For each platform in the plugin's `platforms`, all of `plugins/core/targets.json` when absent: `uv pip install --python-version <python> --python-platform <target> --only-binary :all: --require-hashes -r requirements.txt --target <dir>`. A failure names the package and the platform: that version publishes no wheel there, so pick another version or package.
  - No top-level module or package in the folder has the name of a module its installed dependencies provide. The plugin's folder comes before `site-packages` on the path, so such a file would hide the real library.
  - Compare the installed files across platforms. The same files make one `any` tarball; different files make one tarball per platform.
  - Each tarball is at most 100 MB, or the size on the plugin's line in `plugins/core/SIZE-EXCEPTIONS`.
  - Licenses: read each installed package's license metadata. Every plugin is Apache-2.0 and we redistribute its dependencies in the tarball, so the rule is the Apache Software Foundation's for what an Apache-2.0 work may include. Permissive licenses (their Category A: MIT, BSD, Apache-2.0, ISC, PSF and the like) pass. Weak copyleft (their Category B: MPL, EPL, CDDL) passes, since installed wheels are shipped unmodified. GPL, LGPL, AGPL, SSPL, non-commercial terms, no license, or one the check does not recognise, fail.
  - `pip-audit` over `requirements.txt`. A known vulnerability fails.
- `plugins/core/build/` has a `check` command that runs the tree rules and the build rules on one folder. The contributor guide tells authors to run it before opening a pull request, so CI tells them nothing new.
- `plugins/core/targets.json` as the protocol describes it. The interpreter stream reads the Python version from it.
- A plugin folder is a direct child of `plugins/` that holds a `plugin.json`; the workflows and the build tool treat nothing else as one.
- `plugins/core/RESERVED` is one id per line. It starts with `core`, the one folder under `plugins/` that is not a plugin: it holds everything maintainers own. `example` is not reserved. Add a line when we ship a paid plugin, in the same pull request as that plugin.
- `plugins/core/SIZE-EXCEPTIONS` is one line per plugin, `<id> <megabytes> <reason>`. A maintainer adds the line.
- Workflow `plugin-check.yml` on pull requests that touch `plugins/**`, `.github/workflows/plugin-*.yml` or `.github/CODEOWNERS`. It runs the tree rules and then the build rules on each changed `plugins/<id>/`, and fails the job with their lines. It sets `allow_reserved` when the pull request's `author_association` is `OWNER` or `COLLABORATOR`: MODSetter/SurfSense belongs to a user account, so its maintainers are never `MEMBER`. It does not start Electron and does not run a plugin's `tests/`.
- Review of the SDK and the lifecycle, as [`../02-extending.md`](../02-extending.md#growing-the-sdk-together) describes: `.github/CODEOWNERS` gains two lines naming the maintainers, one for `plugins/core/` and one for `.github/workflows/plugin-*.yml`, and `dev` requires code-owner approval. Branch protection on `dev` could not be read while writing this, so check it first. If code-owner approval cannot be required there, `plugin-check.yml` adds a job, rerun on `pull_request_review`, that fails a pull request touching those paths until a maintainer has approved it. That job is a weaker stand-in, since a pull request can edit the workflow that runs it; the branch rule is the real gate. A plugin folder itself needs no such line: any maintainer's review is enough.
- The checker does not read imports and does not fail on a socket call.

## Acceptance

- A fixture folder that is valid produces no errors.
- One test per tree rule, each with the smallest folder that breaks that rule and the error string that names it.
- A second copy of `example`'s id in another folder is an error.
- A `requirements.txt` line `requests==2.32.3` with its hash is valid. Without the hash it is not. `requests>=2` is not.
- An input of an unknown kind, and a secret without a `title`, each fail with a line naming it.
- A pull request touching `plugins/core/sdk/` passes only once a maintainer has approved it.
- A plugin with its own `json.py`, or with a `requests.py` while depending on `requests`, fails with a line naming the clash. The same code moved into a package named after the plugin passes.
- A reserved id fails without `allow_reserved` and passes with it. `access: paid` on an id that is not reserved fails either way.
- A plugin that needs only `requests` builds one `any` tarball. One that needs `lxml` builds three, and the Windows one contains a `.pyd`.
- A dependency published only as a source distribution fails, naming the package and the platform.
- A tarball over 100 MB fails, and passes once `plugins/core/SIZE-EXCEPTIONS` names the plugin with a larger size.
- A package with no license metadata fails. A GPL dependency fails. An MPL-2.0 one passes.
- A plugin folder with its own `LICENSE` fails.

## Needs from

The protocol's manifest table and `plugins/core/targets.json`. Nothing from the app.
