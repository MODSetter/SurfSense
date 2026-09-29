# Install — install, update and uninstall

> Owns: `modules/plugins/install.py`, `modules/plugins/catalog.py`, `modules/plugins/choose_version.py`, the `installed_plugins` table, the two built-in egress hosts.
> Contract: [`../01-protocol.md`](../01-protocol.md). Versioning: [`../04-versioning.md`](../04-versioning.md). Publishing: [`../release/03-publishing.md`](../release/03-publishing.md).

## Goal

The app lists only plugin versions it can run, installs without running plugin code and without running `pip`, keeps one version on disk, stops a blocked version with a reason and a way out, and removes a plugin without touching the user's documents.

## Work

- `installed_plugins` table: `id` primary key, `version`, `download` (the key it came from), `installed_at`. Hand-written migration.
- `choose_version.py` answers one question for one plugin: which version, and which of its files, should this app run? It applies the rule in [`../04-versioning.md`](../04-versioning.md#which-version-an-app-runs) with the app's own version and this system's key from `system_key()` ([`../python/01-interpreter.md`](../python/01-interpreter.md)). It returns the version and its download, or none with the reason. A version is not run when any entry of its `blocked` list applies to this app.
- The app's own version reaches the backend from Electron, which knows it as `app.getVersion()`: `pythonEnv` in `electron/src/main/sidecars/python.ts` passes it to the API and the workers as `SURFSENSE_LOCAL_APP_VERSION`. `bump-version.sh` writes the version into `backend/pyproject.toml`, which nothing reads at run time, so that is not a source. The variable never reaches a plugin: the runner's allowlist drops every `SURFSENSE_LOCAL_` name. Listing, installing, updating and starting a run all ask it, so the list never offers what install would refuse.
- `catalog.py` holds the catalog: the copy bundled with the app, and a refreshed copy kept at `<data>/plugins/plugin-catalog.json`. A copy whose `schema_version` this app does not know is ignored. Of the others, the higher `released_with` wins, then the later `generated_at`, as the protocol explains. Refresh downloads the live catalog from the URL compiled into the app. It runs when the user asks for it, and before every install or update, which need the same two hosts, so a version withdrawn since the last refresh is never installed. A version whose `url` does not start with `https://github.com/SurfSense-Inc/surfsense-plugin-releases/releases/download/` is dropped.
- Egress: add `host:github.com` and `host:release-assets.githubusercontent.com` to `BUILT_IN` in `modules/egress/service.py`, one row per host as [ADR 0027](../../../adr/0027-egress-consent-per-host.md) requires, off by default. GitHub redirects every release download from the first to the second. Refresh and install need both, and the consent prompt asks for them together. It names both errands, refreshing the plugin list and downloading plugins, and what they send: the id and version of the plugin, and the IP address. The same pull request updates [`egress.md`](../../../architecture/egress.md), which describes `BUILT_IN` and `list_destinations()`.
- Settings → Network lists what `list_destinations()` returns, which today is the built-in hosts and the hosts of model connections. It also returns every host declared by an installed plugin, with the plugins that declare it, and every host already allowed whatever declared it. Without the first, a plugin's grant could not be seen or revoked; without the second, a grant would stay on but vanish from the list once the plugin that asked for it is uninstalled.
- Install, given a plugin:
  1. Ask `choose_version.py`. With no answer, refuse with its reason.
  2. `access: paid` consults the stored license state, `status()` in `modules/license/service.py`. Missing, expired, or `clock_untrusted` refuses with `license_required`. A `trial` license unlocks it for its term. `free` does not consult it.
  3. Require both hosts allowed, otherwise raise the existing `EgressDeniedError` naming both, before any connection opens.
  4. Download the `url`. Follow a redirect only to `release-assets.githubusercontent.com`, and reject any other host before writing. Stop reading past the download's `size`.
  5. Compare sha256. Extract with the path rules in the protocol. Compare the packaged `plugin.json` to the catalog version's `manifest` and `version`. Rename into place.
  6. Insert or update `installed_plugins`. Create `<data>/plugins/<id>/data` if it is absent.
- Update is an install of the version `choose_version.py` picks when it is newer than the installed one. Once the new version is in place, delete the previous version directory. If a `queued` or `running` run still uses it, leave it: at every start, the app deletes each version directory that is not the installed one. No backup is kept: the catalog still has every version.
- An installed version this app must not run, because it is blocked for this app or because it is newer than the app after a downgrade, cannot start a run. The refusal carries the reason, and the app offers the version `choose_version.py` picks instead, which may be older. Moving to an older version is the same install; the plugin's data directory stays, and the contributor guide asks plugins to cope with data a newer version wrote, or to start over.
- A plugin with `removed_from_app` at or below the app's version is not listed. An installed copy keeps running unless a version of it is blocked.
- Uninstall: cancel the plugin's `queued` and `running` runs and wait for them to stop. Then delete `<data>/plugins/<id>/`, which holds the version and `data`, delete the `installed_plugins` row, and delete the plugin's rows in `plugin_secrets`. Do not delete documents: they are the user's, whatever put them there.

## Acceptance

- A file with a `../` member extracts nothing and leaves no directory behind.
- A sha256 mismatch leaves no directory behind.
- A packaged `plugin.json` whose `hosts` or `version` differ from the catalog's is rejected.
- A redirect to any host but `release-assets.githubusercontent.com` is rejected and the body is not saved.
- Install with either host not allowed raises `EgressDeniedError` naming both and does not open a connection.
- A `paid` plugin with no license does not insert `installed_plugins`. With a trial license, it installs. The same plugin with `access: free` does, with no license on disk.
- On SurfSense 2.4.0, with versions 2.3.0, 2.4.0 and 2.5.0 in the catalog, `choose_version.py` picks 2.4.0. With 2.4.0 blocked, it picks 2.3.0.
- A version with only a `cp312-windows-x64` download is not chosen on Linux. A version with only `any` is chosen everywhere, unless its `platforms` leaves this system out.
- A version blocked from 2.6.0 still runs on 2.5.0 and is refused on 2.6.0, where the app offers the newest version it can run.
- After a downgrade below the installed version, the installed version is refused and an older version is offered.
- Updating leaves exactly one version directory. With a run still using the old one, two remain until that run ends, and one after the next start.
- A refreshed catalog survives a restart, and loses to a bundled copy with a later `generated_at`. A refreshed copy with an unknown `schema_version` is ignored.
- A host allowed for an installed plugin is listed with the plugin's name. After uninstalling it, the host is still listed while it stays allowed.
- Uninstall during a run stops the run first, then removes the folder and the secret, and leaves a note that the plugin created.

## Needs from

The manifest rules in `plugins/core/manifest/` ([`../release/02-pull-request-checks.md`](../release/02-pull-request-checks.md)). `system_key()` from the interpreter stream. The egress module and the license verifier, which exist. A local fixture server stands in for `surfsense-plugin-releases` until [`../release/03-publishing.md`](../release/03-publishing.md) has published a real catalog.
