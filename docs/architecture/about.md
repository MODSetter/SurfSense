# About

Settings › About, in the dialog's App group, shows which build is running and where to get help: the version, the update controls, links, the license, and details for a bug report.

**Code:** [`surfsense_local/frontend/src/features/about/`](../../surfsense_local/frontend/src/features/about/), [`surfsense_local/electron/src/main/about/`](../../surfsense_local/electron/src/main/about/), [`surfsense_local/electron/src/main/external-url.ts`](../../surfsense_local/electron/src/main/external-url.ts)

## What it shows

- The version, from `app.getVersion()` in the main process, read through `window.surfsense.about.details()`. The same call returns the OS, architecture, and the Electron, Chromium and Node versions.
- The update controls ([updates](updates.md)), which moved here from General.
- Links: release notes for the running version (`/releases/tag/v<version>`), the docs on `surfsense.com`, the GitHub repository, the Discord invite, and a new bug report on the `bug.yml` form with the system details prefilled in its `what` field.
- The license line, Apache 2.0, linking to `LICENSE` on GitHub.
- Troubleshooting: Copy system info puts the version, OS and runtime versions on the clipboard, in English whatever the interface language, since it is pasted into issues.

## Links

Every link opens in the OS browser, only on a click, through `shell:open-external`. The main process opens only `surfsense.com`, the `MODSetter/SurfSense` repository on GitHub, and the Discord invite, and drops anything else ([egress](egress.md)). A link added here that falls outside that list does nothing until the list grows.

Outside the desktop app there is no bridge: the version, release notes, bug report and troubleshooting rows are hidden, and the remaining links are plain anchors.

## Known gaps

- No third-party license notices ship with the app. Generating them needs the frontend's npm dependencies, the Python sidecars' packages and the bundled native binaries collected at build time.
- The app writes no log files, so there is no logs folder to open. This run's output is kept in memory and shown in Report issue ([issue reports](issue-reports.md)), and is gone once the app quits.
