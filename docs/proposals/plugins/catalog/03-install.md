# Catalog — install, update and uninstall

> Owns: `modules/plugins/install.py`, `modules/plugins/catalog.py`, `modules/plugins/downloads.py`, the `installed_plugins` table, the two built-in egress hosts.
> Contract: [`../01-protocol.md`](../01-protocol.md). Checker: [`01-manifest-and-ci.md`](01-manifest-and-ci.md). Publishing: [`02-publish.md`](02-publish.md).

## Goal

The app lists only what it can install, installs without running plugin code and without running `pip`, keeps one version on disk, and removes a plugin without touching the user's documents.

## Work

- `installed_plugins` table: `id` primary key, `version`, `download` (the key it came from), `installed_at`. Hand-written migration.
- `downloads.py` picks the download. When the entry has `platforms` and this system's platform is not in it, there is none. Otherwise it is the entry's download for the app's own key, from `system_key()` in [`../python/01-interpreter.md`](../python/01-interpreter.md), else `any`, else none. Listing, installing and updating all call this one function, so the list never offers what install would refuse.
- `catalog.py` holds the catalog: the bundled copy, and a refreshed copy kept at `<data>/plugins/catalog.json`. The one with the later `generated_at` wins, so an app update's newer bundled copy is not hidden by an old refresh. Refresh reads the compiled reference `ghcr.io/modsetter/surfsense/plugins:latest`: its manifest, then its one file. An entry with a `url` outside `https://ghcr.io/v2/modsetter/surfsense/plugins/<its id>/blobs/` is dropped.
- Egress: add `host:ghcr.io` and `host:pkg-containers.githubusercontent.com` to `BUILT_IN` in `modules/egress/service.py`, one row per host as [ADR 0027](../../../adr/0027-egress-consent-per-host.md) requires, off by default. Refresh and install need both, and the consent prompt asks for them together. It names both errands, refreshing the plugin list and downloading plugins, and what they send: the id and version of the plugin, and the IP address.
- Settings → Network lists what `list_destinations()` returns, which today is the built-in hosts and the hosts of model connections. It also returns every host declared by an installed plugin, with the plugins that declare it, and every host already allowed whatever declared it. Without the first, a plugin's grant could not be seen or revoked; without the second, a grant would stay on but vanish from the list once the plugin that asked for it is uninstalled.
- The app's SDK version, for every `sdk` range, is `sdk_version()` from [`../python/01-interpreter.md`](../python/01-interpreter.md).
- Install, given an entry:
  1. Refuse what the list would not offer: no download for this system, an `sdk` range this app does not satisfy (`needs_newer_app`), or a yanked version (`yanked`, with its reason).
  2. `access: paid` consults the stored license state, `status()` in `modules/license/service.py`. Missing, expired, or `clock_untrusted` refuses with `license_required`. A `trial` license unlocks it for its term. `free` does not consult it.
  3. Require both hosts allowed, otherwise raise the existing `EgressDeniedError` naming both, before any connection opens.
  4. Download the `url` with `Authorization: Bearer QQ==`, the anonymous pull Homebrew uses. Follow a redirect only to `pkg-containers.githubusercontent.com`, and reject any other host before writing. Stop reading past the download's `size`.
  5. Compare sha256. Extract with the path rules in the protocol. Compare the manifest inside the tarball to the catalog fields. Rename into place.
  6. Insert or update `installed_plugins`. Create `<data>/plugins/<id>/data` if it is absent.
- Update is an install of the catalog's newer version over an installed one. Once the new version is in place, delete the previous version directory. If a `queued` or `running` run still uses it, leave it: at every start, the app deletes each version directory that is not the installed one. No backup and no rollback: nothing would use a backup, and the data directory may already be in the newer version's format. Homebrew's `brew upgrade` removes the old version the same way.
- Before a run is enqueued, the API refuses an installed version that is yanked, with its reason, or whose `sdk` range this app no longer satisfies.
- Uninstall: cancel the plugin's `queued` and `running` runs and wait for them to stop. Then delete `<data>/plugins/<id>/`, which holds the version and `data`, delete the `installed_plugins` row, and delete secrets named `plugin:<id>:*`. Do not delete documents: they are the user's, whatever put them there.

## Acceptance

- A tarball with a `../` member extracts nothing and leaves no directory behind.
- A sha256 mismatch leaves no directory behind.
- A manifest whose `hosts` differ from the catalog entry is rejected.
- A redirect to any host but `pkg-containers.githubusercontent.com` is rejected and the body is not saved.
- Install with either host not allowed raises `EgressDeniedError` naming both and does not open a connection.
- A `paid` entry with no license does not insert `installed_plugins`. With a trial license, it installs. The same entry with `access: free` does, with no license on disk.
- An entry with only a `cp312-windows-x64` download is not listed on Linux, and installing it there is refused. An entry with only `any` installs everywhere, unless its `platforms` leaves this system out: an `any` entry with `platforms: ["macos-arm64"]` is not listed on Windows.
- Updating leaves exactly one version directory. With a run still using the old one, two remain until that run ends, and one after the next start.
- An installed version that is yanked cannot start a run, and the refusal carries the reason.
- A host allowed for an installed plugin is listed with the plugin's name. After uninstalling it, the host is still listed while it stays allowed.
- A refreshed catalog survives a restart, and loses to a bundled copy with a later `generated_at`.
- Uninstall during a run stops the run first, then removes the folder and the secret, and leaves a note that the plugin created.

## Needs from

The manifest checker. `system_key()` from the interpreter stream. The egress module and the license verifier, which exist. A local fixture server stands in for ghcr.io until [`02-publish.md`](02-publish.md) has published a real catalog.
