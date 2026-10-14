# Office pack

Office support is LibreOffice, run by the backend on copies of Word, Excel and PowerPoint files to lay them out as PDF, recalculate workbooks and convert between formats. It is never part of the installer. The user turns it on in Settings, which downloads The Document Foundation's own build for this platform, pinned by sha256, after they allow its host; or they confirm a LibreOffice they already have. Nothing downloads at launch, on update, or because a feature would like a render.

**Code:** [`surfsense_local/backend/modules/runtime_packs/office/`](../../surfsense_local/backend/modules/runtime_packs/office/)
**Design:** [04 runtime and packs](../proposals/file-agent/04-runtime-and-packs.md), sections 6 and 7

## The pin

[`pin.py`](../../surfsense_local/backend/modules/runtime_packs/office/pin.py) is the one place that names the download: `HOST`, and one `PackFile` per platform key (`windows-x64`, `macos-x64`, `macos-arm64`, `linux-x64`, `linux-arm64`) with its version, URL, sha256, size and packaging. URLs are on TDF's permanent archive, `downloadarchive.documentfoundation.org/libreoffice/old/`, because the stable folder drops a version two point releases later. Moving the pack to SurfSense's own release repository changes this file only.

| Platform | Version | Packaging | sha256 source |
|---|---|---|---|
| Windows x64 | 26.8.0.3 | MSI, unpacked as an administrative image | downloaded and hashed on the development machine; matches TDF's published hash |
| macOS x64, arm64 | 26.8.1.1 | DMG, `LibreOffice.app` copied out unchanged | TDF's `.mirrorlist` |
| Linux x64, arm64 | 26.8.1.1 | tarball of `.deb` files, unpacked without dpkg | TDF's `.mirrorlist` |

Windows is on 26.8.0 because 26.8.1 has no Windows build: TDF's stable folder lists one that answers 404, and the archive's 26.8.1.1 folder has no `win/`. `SUPPORTED_BRANCHES` lists the branches an installed LibreOffice may be on, with the day each stops getting fixes: 26.2 until 30 Nov 2026, 26.8 until 13 Jun 2027.

## Turning it on

`POST /runtime-packs/office/install` checks `egress.require("host:downloadarchive.documentfoundation.org")` before any connection opens, so the first answer is a `403 egress_disabled` naming that host, which the interface turns into a consent dialog ([egress](egress.md)). Once allowed, the install runs in the API in its own slot, never queued behind a model download:

1. **Download** ([`download.py`](../../surfsense_local/backend/modules/runtime_packs/office/download.py)) to `<data>/runtime/office/downloads/<file>.part`, resuming with `Range`. The archive answers with a redirect to one of TDF's mirrors; redirects are followed by hand, https only, at most three. Bytes past the pinned size stop the download and delete the `.part`; a sha256 that does not match deletes it too.
2. **Unpack** into `versions/<version>.staging-<pid>-<random>/`, a folder of its own for each attempt ([`unpack/`](../../surfsense_local/backend/modules/runtime_packs/office/unpack/)). Windows runs `msiexec /a` with `TARGETDIR`: no product is registered, nothing is written outside the folder, and no elevation is needed (measured on 26.8.0: 36 s, 1.2 GB unpacked). macOS mounts the DMG read-only and copies the app with `ditto`. Linux reads each `.deb` in `DEBS/` as an ar archive and extracts its data with tarfile's `data` filter; `DEBS/desktop-integration/` is skipped because it links into `/usr`.
3. **Check**: one DOCX to PDF through the runner, from the staging folder. A failed unpack or check deletes the staging folder at once. msiexec, tar and the check's soffice cannot be stopped midway, so a cancel during either, or a second cancel after it, waits for it to end, then deletes the staging folder; until then the install still counts as running.
4. **Switch**: a leftover `versions/<version>/` that no record names is renamed aside and deleted, never deleted in place; a refused rename fails the install with `in_use` and deletes the staging folder. The staging folder is renamed to `versions/<version>/`, `installed.json` names it, the download is deleted, and older versions are removed.

Staging folders left by an install the app quit during, and removed folders, are deleted the next time the installer starts. `POST /runtime-packs/office/install` refuses while an install runs (`409 already_running`, checked after its last await, so two requests cannot both start one) and while the pack is installed (`409 already_installed`): a reinstall would replace the folder a LibreOffice run may be using. `DELETE /runtime-packs/office` cancels a running install, keeping the `.part`; otherwise it renames the pack's folder to `.removed-<ts>`, then forgets the pack and a confirmed LibreOffice, then deletes the folder. On Windows the rename fails while LibreOffice holds a file, and the route answers `409 in_use` with nothing forgotten.

## An installed LibreOffice

[`detect.py`](../../surfsense_local/backend/modules/runtime_packs/office/detect.py) looks only at fixed install locations: on Windows `HKLM\SOFTWARE\LibreOffice\UNO\InstallPath`, then `%ProgramFiles%\LibreOffice`; on macOS `/Applications` and `~/Applications`; on Linux `/usr/lib`, `/usr/lib64` and `/opt/libreoffice*`. PATH and `HKCU` are not read. It reads the branch from the install's bootstrap file (`ProductKey=LibreOffice 26.8`) and refuses, with a code Settings shows:

| Code | Means |
|---|---|
| `branch_unsupported` | the branch is not in `SUPPORTED_BRANCHES`, such as 25.2 |
| `branch_ended` | the branch is listed and its end date has passed |
| `shared_extensions` | `share/uno_packages/cache/uno_packages/` is not empty, or `share/extensions/` holds something other than TDF's dictionaries, `nlpsolver` and `wiki-publisher` |
| `branch_unknown`, `program_missing` | the install cannot be read |

Detection reads files only. `POST /runtime-packs/office/use-installed` runs `soffice --version` and the same DOCX check under SurfSense's profile, then writes `use-installed.json` with the path, version and branch. Every later run checks the install again, so one that has moved to an ended branch stops being used.

## The runner

[`soffice/`](../../surfsense_local/backend/modules/runtime_packs/office/soffice/) is what features call, from workers, outside a database transaction and outside the engine child:

- `convert(source, target_format, out_dir, *, deadline, runtime=None) -> Path` writes `<out_dir>/<stem>.<format>` for `pdf`, `docx`, `xlsx` or `pptx`.
- `recalc(xlsx, *, deadline, runtime=None) -> Recalculated` returns every formula cell's value, by sheet and cell, with error results apart, after LibreOffice recalculated a copy. The workbook LibreOffice wrote is thrown away.
- `report_version(runtime, *, deadline) -> str`, run under the lock and in a process tree like a conversion, so a hung `--version` is killed with everything it started.

`runtime` defaults to `office_runtime()` in [`runtime.py`](../../surfsense_local/backend/modules/runtime_packs/office/runtime.py): the pack, then a confirmed install, else `OfficeMissing` with the reason. Tests name a runtime explicitly; nothing finds a LibreOffice on its own.

Each run:

- **Copies** the file into a fresh folder under `<data>/runtime/office/tmp/` and neutralizes the copy ([`render_copy.py`](../../surfsense_local/backend/modules/runtime_packs/office/soffice/render_copy.py)): every external relationship target becomes `about:invalid`, `INCLUDETEXT`, `INCLUDEPICTURE`, `LINK`, `DDE` and `DDEAUTO` fields lose their instruction and keep their last result, DDE links lose their program and topic, and data connections lose their URL. Elements match under any namespace prefix, since LibreOffice reads them by namespace. The XML is edited as text, UTF-8 or UTF-16 as the part was, so untouched parts keep their bytes; a part that is neither raises `OfficeFailed`.
- **Waits** for `<data>/runtime/office/run.lock`, an OS file lock shared by every process, until 20 s before the caller's monotonic deadline, then raises `OfficeBusy` without starting anything.
- **Runs** `soffice.com` (Windows), `program/soffice` (Linux) or `Contents/MacOS/soffice` (macOS) with `-env:UserInstallation` pointing at `<data>/runtime/office/profiles/slot-0`, `--headless --invisible --nodefault --nolockcheck --nologo --norestore --convert-to`, in an environment built from scratch: the OS basics, `HOME` in the profile, proxies at `http://127.0.0.1:9`, never `SURFSENSE_LOCAL_SECRET` or `LIBO_UPDATER_*`. The process and everything it starts are bound to a Windows job object or a POSIX process group (`worker/document_script/kill_process_tree.py`).
- **Limits** the run to the smaller of 90 s and the time left, then kills the tree and raises `OfficeTimeout`. A timeout, or a failure that mentions the profile, retries once with a freshly seeded profile when at least 30 s remain.
- **Succeeds** only on an output file that starts with `%PDF-` or a zip header; the exit code is not trusted. Anything else is `OfficeFailed` with LibreOffice's last line.

The profile ([`profile.py`](../../surfsense_local/backend/modules/runtime_packs/office/soffice/profile.py)) is seeded before LibreOffice first opens it. Measured on 25.2.7.2, LibreOffice keeps every key when it writes the profile back:

| Key | Value |
|---|---|
| `Calc/Formula/Load` `OOXMLRecalcMode`, `ODFRecalcMode` | 0, always recalculate |
| `Update/Update` `Enabled`; `Jobs` `UpdateCheck` `AutoCheckEnabled`, `AutoDownloadEnabled` | false: updates off three ways |
| `Common/Security/Scripting` `MacroSecurityLevel`, `DisableMacrosExecution`, `BlockUntrustedRefererLinks`, `SecureURL` | 3, true, true, empty |
| `Calc/Content/Update` `Link`, `Writer/Content/Update` `Link` | 1 and 2, never |
| `Inet/Settings` proxy type, HTTP and HTTPS proxy | manual, `127.0.0.1:9` |

On the development machine, 25.2.7.2 converted a python-docx DOCX and a python-pptx PPTX to PDF, recalculated an xlsxwriter workbook's cached zeros to 6 and 110, and kept its `version.ini` build id; the pinned 26.8.0.3 MSI unpacked and converted the same way.

## Routes

| Route | Does |
|---|---|
| `GET /runtime-packs/office` | the state: `not_installed`, `downloading`, `unpacking`, `checking`, `installed`, `using_installed` or `error`, with `version`, `path`, `progress`, `error {code, message}`, `offer {version, size, host, destination}`, `detected {path, branch, usable, refusal}` and `offer_dismissed` |
| `GET /runtime-packs/office/events` | the same, as NDJSON: now, on each change, and every 15 s |
| `POST /runtime-packs/office/install` | `202`; `403 egress_disabled`, `409 already_running` or `already_installed`, `422 unsupported_platform` |
| `POST /runtime-packs/office/use-installed` | `200`; `404 not_found`, `409` with a detection code or `smoke_failed` |
| `DELETE /runtime-packs/office` | cancel, forget or remove; `409 in_use` |
| `POST /runtime-packs/office/offer/dismiss` | `200`; agent threads stop offering Office support on this install |

Install failures carry `download_failed`, `checksum_mismatch`, `insecure_redirect`, `too_many_redirects`, `too_large`, `unpack_failed`, `smoke_failed` or `install_failed`.

## Settings

Settings › System › Office support ([`features/office-support/`](../../surfsense_local/frontend/src/features/office-support/)) follows `GET /runtime-packs/office/events` while it is open. Off, it offers Turn on, which opens a consent dialog naming LibreOffice's version, its size in MB from `offer`, The Document Foundation, the host and that the archive may hand the download to a mirror, and what is sent: the IP address and the file's name. Download allows `offer.destination` in egress and then starts the install, so the `403 egress_disabled` does not come up; Not now changes nothing. While it installs, a progress bar names the phase and Cancel sends `DELETE`. On, it reads "On: LibreOffice <version>", with the path for the user's own install, and Remove or Stop using it. A LibreOffice found at a fixed path shows with "Use the LibreOffice I have" when `usable`, or with the reason it cannot be used. Every code above has its own sentence, in all ten languages. Settings › Network lists the host as "Office support download".

## The offer in an agent thread

Under the latest reply in a thread that made a Word, Excel or PowerPoint file (a render or a revised copy whose artifact's format is `docx`, `xlsx` or `pptx`), while Office support is `not_installed` and offered for this computer, the thread shows a small offer: exact Office pages, real spreadsheet totals and conversion to PDF, and the download's size in MB from `offer` ([`office-offer-banner.tsx`](../../surfsense_local/frontend/src/features/office-support/office-offer-banner.tsx)). Its button opens Settings › Office support with the consent dialog already open, or without it when a `usable` LibreOffice was `detected`, so "Use the LibreOffice I have" is not hidden behind a download; it never downloads anything itself; its close button calls `POST /runtime-packs/office/offer/dismiss`. `offer_dismissed` is true from then on, and also once Office support was on, pack or confirmed install, even after it is removed: the backend keeps `<data>/runtime/office/offer-dismissed.json`, which a removal leaves, written by the dismissal and with `installed.json` or `use-installed.json` ([`records.py`](../../surfsense_local/backend/modules/runtime_packs/office/records.py)). Onboarding does not offer it.

## What uses it

Features reach LibreOffice only through [`modules/office_support/`](../../surfsense_local/backend/modules/office_support/): `office_engine()` is None while Office support is off, and every caller then keeps its old path; a busy, timed-out or failed run is an `OfficeRunError` whose sentence the caller's report carries.

| Feature | Process | Without Office support |
|---|---|---|
| A Word or PowerPoint version's page previews in the render result, and `surfsense_source_pages` for Word and PowerPoint sources ([agent](agent.md#previews)) | API, at most 60 s | Electron prints the file with the in-app viewer's library |
| A workbook the agent's script wrote: formula values cached in the delivered file ([studio](studio.md#script-documents)) | Studio worker, after the run, at most 45 s | delivered as the script wrote it; the result says the values were not recalculated |
| `surfsense_convert_document`: a Word or PowerPoint version, or a ticked source, as a new PDF ([agent](agent.md#converting-to-pdf), [studio](studio.md#converted-pdfs)) | Studio worker, at most 120 s | refused in a sentence naming Settings |

## Known gaps

- The pack is TDF's whole build, not the trimmed one the design describes: 1.2 GB unpacked on Windows against 489 MB trimmed.
- The macOS and Linux unpackers have only run against synthetic archives; neither has unpacked TDF's real file.
- The download is allowed by one host, but its bytes come from whichever TDF mirror the archive redirects to, which sees the user's IP address. The sha256 vouches for the bytes, not for the mirror.
- No Install from file for machines that never go online, and no Update offer when a newer app carries a newer pin.
- The resource usage panel counts `soffice.bin` as the interface.
