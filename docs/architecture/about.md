# About

Settings › About, in the dialog's App group, shows which build is running and where to get help: the version, the update controls, links and the license. Bug reports and Copy system info are in Settings › Report issue ([issue reports](issue-reports.md)).

**Code:** [`surfsense_local/frontend/src/features/about/`](../../surfsense_local/frontend/src/features/about/), [`surfsense_local/electron/src/main/about/`](../../surfsense_local/electron/src/main/about/), [`surfsense_local/electron/src/main/external-url.ts`](../../surfsense_local/electron/src/main/external-url.ts)

## What it shows

- The version, from `app.getVersion()` in the main process, read through `window.surfsense.about.details()`. The same call returns the OS, architecture, and the Electron, Chromium and Node versions. The Docker image has no bridge, so its frontend is built with `VITE_SURFSENSE_VERSION` from `surfsense_local/VERSION`, the one version it shares with the desktop app.
- The update controls ([updates](updates.md)), which moved here from General, and below them the Usage statistics switch ([usage statistics](usage-statistics.md)). Each has "Show exactly what's sent": the last update request with its headers, and the next and last usage reports.
- Your data: the folder that holds models, workspaces and settings, `~/.surfsense`, which the install folder does not, with **Open folder** to show it in the file manager. Main returns the path only to the app's own window, through `window.surfsense.about.dataFolder()`, and opens it with `shell.openPath` ([`data-folder-ipc.ts`](../../surfsense_local/electron/src/main/about/data-folder-ipc.ts)). It is not part of the details Copy system info puts in a report, since it names the user's home folder.
- Links: release notes for the running version (`/releases/tag/v<version>`), the docs on `surfsense.com`, the GitHub repository, and the Discord invite.
- The license line, Apache 2.0, linking to `LICENSE` on GitHub.

## Links

Every link opens in the OS browser, only on a click, through `shell:open-external`. The main process opens only `surfsense.com`, the `MODSetter/SurfSense` repository on GitHub, and the Discord invite, and drops anything else ([egress](egress.md)). A link added here that falls outside that list does nothing until the list grows.

A link to `surfsense.com`, here, in Settings › License and in Settings › General's cloud import, carries `utm_source=desktop`, `utm_medium=app`, `utm_content` naming the place it was opened from (`about_docs`, `license_pricing`, `license_renew`, `license_trial`, `cloud_import`) and `app_version` once the version is read ([`site-visit-url.ts`](../../surfsense_local/frontend/src/features/external-links/site-visit-url.ts)). Nothing else is added, and links to GitHub and Discord stay plain.

Outside the desktop app there is no bridge: the data folder row is hidden, the version and release notes show only in a build given `VITE_SURFSENSE_VERSION`, and the links are plain anchors.

## Known gaps

- The app does not show its third-party license notices. They are generated at build time and ship as `resources/licenses/THIRD_PARTY_NOTICES.json` and `.txt` ([packaging](packaging.md#third-party-notices)), but nothing in Settings › About opens them yet.
- The app writes no log files, so there is no logs folder to open. This run's output is kept in memory and shown in Report issue ([issue reports](issue-reports.md)), and is gone once the app quits.
