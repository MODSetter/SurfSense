# Release — pull-request checks

> Owns: `plugins/core/manifest/`, `plugins/core/checks/`, `plugins/core/policy/reserved-plugin-ids.txt`, `.github/workflows/plugins-pull-request-checks.yml`, `.github/workflows/plugins-weekly-security-audit.yml`, the plugin lines in `.github/CODEOWNERS`.
> Contract: [`../01-protocol.md`](../01-protocol.md). Packaging: [`01-packaging.md`](01-packaging.md). Why the checks matter to versioning: [`../04-versioning.md`](../04-versioning.md).

## Goal

A bad plugin folder, or an SDK change that would break a plugin, fails in CI before anyone reviews it, with a message its author can act on, and the author can run the same checks first. The manifest rules live once, in a small package the app uses at install too.

## Work

- `plugins/core/manifest/` is a small package that depends only on pydantic and the standard library: `load_manifest(path) -> Manifest` and `check_tree(folder, reserved, allow_reserved) -> list[str]`. Empty list means the folder may be merged. The strings are the review comment. The checks import it, and the backend takes it as a path dependency in its `pyproject.toml`, so the frozen app carries the same rules without the tooling pulling in the backend's own dependencies.
- A plugin folder is a direct child of `plugins/` that holds a `manifest.json`; the workflows and the tooling treat nothing else as one.
- Tree rules, all of them, and no others:
  - `manifest.json` matches the protocol tables, including `platforms` against `plugins/core/build-targets.json` and `timeout_seconds` within its range. A host with a scheme, port, path or wildcard, or a loopback name, is an error. A `version` or compatibility field is an error that says the release sets it.
  - Every input has a legal, unique name, a `title`, and a `kind` of `string`, `number` or `boolean`. Every secret has a legal, unique name and a `title`.
  - `id` equals the folder name, and is not the id of a plugin the live catalog marks `removed_from_app`: a published id is never reused.
  - An id listed in `plugins/core/policy/reserved-plugin-ids.txt`, or starting with `surfsense-`, passes only with `allow_reserved`. `access: paid` passes only on such an id.
  - `requirements.in` and `requirements.txt` are both present or both absent. Every requirement in `requirements.txt` is pinned with `==` and carries a `--hash`. No URL, no editable install, no `--index-url`, `--extra-index-url` or `--find-links`.
  - `main.py` exists. No `LICENSE` or other license file of the plugin's own: plugins are Apache-2.0 under the repository's license. No `site-packages/` in git.
  - No top-level module or package in the folder is named like a standard-library module (`sys.stdlib_module_names`) or `surfsense_plugin`. The line names the clash and suggests a package named after the plugin.
- Build rules, through [`01-packaging.md`](01-packaging.md) without uploading anything:
  - The plugin packages for every platform it supports, within its size limit.
  - No top-level module or package in the folder has the name of a module its installed dependencies provide. The plugin's folder comes before `site-packages` on the path, so such a file would hide the real library.
  - Licenses: read each installed package's license metadata. Every plugin is Apache-2.0 and we redistribute its dependencies in its files, so the rule is the Apache Software Foundation's for what an Apache-2.0 work may include. Permissive licenses (their Category A: MIT, BSD, Apache-2.0, ISC, PSF and the like) pass. Weak copyleft (their Category B: MPL, EPL, CDDL) passes, since installed wheels are shipped unmodified. GPL, LGPL, AGPL, SSPL, non-commercial terms, no license, or one the check does not recognise, fail.
  - `pip-audit` over `requirements.txt`. A known vulnerability fails.
- Type check, with pyright. The SDK is checked in strict mode. Each plugin is checked in standard mode against the SDK and its own packaged `site-packages`, so an author annotates nothing: pyright infers their code and still checks every call into the SDK. It catches a function that does not exist, a wrong argument, and misuse of a returned object. pyright is the mature choice; Astral's `ty` would match our tooling, but its README calls it beta and warns of breaking changes, so it is not a gate yet.
- A pull request that touches `plugins/core/sdk/` type-checks every plugin, not only the changed ones. When a plugin fails because of the SDK change, the line names the plugin, file and line, and says: update that plugin in this pull request, or keep what it uses. This is what stops a plugin falling behind the app ([`../04-versioning.md`](../04-versioning.md#why-an-unchanged-plugin-cannot-break-silently)).
- The SDK's contract tests run on any pull request that touches `plugins/core/sdk/` or `surfsense_local/backend/`, against the real backend. They are what catch an app route changing under the SDK; [`../sdk/01-library-and-harness.md`](../sdk/01-library-and-harness.md) owns them.
- `surfsense-plugins check <plugin>` runs the tree rules, the build rules and the type check on one folder. The contributor guide tells authors to run it before opening a pull request, so CI tells them nothing new.
- `plugins/core/policy/reserved-plugin-ids.txt` is one id per line. It starts with `core`, the one folder under `plugins/` that is not a plugin. `example` is not reserved. Add a line when we ship a paid plugin, in the same pull request as that plugin.
- Workflow `plugins-pull-request-checks.yml` on pull requests that touch `plugins/**`, `surfsense_local/backend/**`, `.github/workflows/plugins-*.yml` or `.github/CODEOWNERS`. It runs the checks above that the changed paths call for and fails the job with their lines. It sets `allow_reserved` when the pull request's `author_association` is `OWNER` or `COLLABORATOR`: MODSetter/SurfSense belongs to a user account, so its maintainers are never `MEMBER`. It does not start Electron and does not run a plugin's own `tests/`.
- Review, as [`../02-extending.md`](../02-extending.md#growing-the-sdk-together) describes: `.github/CODEOWNERS` gains lines naming the maintainers for `/plugins/`, `/surfsense_local/backend/modules/plugins/` and `/.github/workflows/plugins-*.yml`, and `dev` requires code-owner approval. Today the only line that covers these paths is `* @MODSetter`, which would make MODSetter the one person able to approve any plugin; naming every maintainer lets any of them approve a plugin folder, while the SDK, the tooling and the lifecycle files still cannot merge without one. Branch protection on `dev` could not be read while writing this, so check it first. If code-owner approval cannot be required there, `plugins-pull-request-checks.yml` adds a job, rerun on `pull_request_review`, that fails a pull request touching those paths until a maintainer has approved it. That job is a weaker stand-in, since a pull request can edit the workflow that runs it; the branch rule is the real gate.
- Workflow `plugins-weekly-security-audit.yml` runs `surfsense-plugins audit` every week: `pip-audit` over every plugin's `requirements.txt`, opening or updating one issue per affected plugin, labelled with its id. The fix is a pull request that updates the lock, and it ships with the next release. When waiting is unsafe, a maintainer blocks the published version ([`03-publishing.md`](03-publishing.md)).
- The checks do not infer hosts from imports and do not fail on a socket call.

## Acceptance

- A fixture folder that is valid produces no errors.
- One test per tree rule, each with the smallest folder that breaks that rule and the error string that names it.
- A second copy of `example`'s id in another folder is an error.
- A `manifest.json` with a `version` fails with the line that says the release sets it.
- A `requirements.txt` line `requests==2.32.3` with its hash is valid. Without the hash it is not. `requests>=2` is not.
- An input of an unknown kind, and a secret without a `title`, each fail with a line naming it.
- A plugin with its own `json.py`, or with a `requests.py` while depending on `requests`, fails with a line naming the clash. The same code moved into a package named after the plugin passes.
- A reserved id fails without `allow_reserved` and passes with it. `access: paid` on an id that is not reserved fails either way.
- A package with no license metadata fails. A GPL dependency fails. An MPL-2.0 one passes.
- A plugin folder with its own `LICENSE` fails.
- A pull request that removes an SDK function a plugin calls fails, naming the plugin, file and line, and passes once that plugin is updated in the same pull request.
- A plugin calling an SDK function with a wrong argument fails the type check; the same plugin with no annotations of its own and correct calls passes.
- A pull request touching `plugins/core/` passes only once a maintainer has approved it, and a plugin folder can be approved by any maintainer.
- A new folder reusing the id of a removed plugin fails.

## Needs from

The protocol, [`01-packaging.md`](01-packaging.md), the SDK's types, and the live catalog for removed ids. Nothing from the rest of the app.
