# Issue reports

Report issue, a tab in Settings' App group below About, and a dialog opened from every error toast, shows what this run of the app has logged and turns the user's description into a GitHub bug report. The tab and the dialog share one form and one draft; toasts keep the dialog because they fire where Settings does not exist, such as onboarding. Help › Report Issue… in the macOS menu bar (Windows and Linux draw no menu bar) opens the Settings tab on the dashboard, which claims it through [`help-menu-report.ts`](../../surfsense_local/frontend/src/features/feedback/help-menu-report.ts), and the dialog on every other screen. The tab also carries Copy system info, which puts the version, OS and runtime versions on the clipboard in English whatever the interface language, since it is pasted into issues.

**Code:** [`surfsense_local/frontend/src/features/feedback/`](../../surfsense_local/frontend/src/features/feedback/), [`surfsense_local/electron/src/preload/index.ts`](../../surfsense_local/electron/src/preload/index.ts), [`surfsense_local/electron/src/main/session-log/`](../../surfsense_local/electron/src/main/session-log/), [`surfsense_local/electron/src/main/menu/`](../../surfsense_local/electron/src/main/menu/), [`.github/ISSUE_TEMPLATE/bug.yml`](../../.github/ISSUE_TEMPLATE/bug.yml)

## The session log

- The main process keeps the newest 2,000 lines of this run in memory, each stamped with the local time and its source: every sidecar's stdout and stderr, by sidecar name, and its stop or crash; the window's console warnings and errors (`renderer`); electron-updater's own log (`updater`). Nothing is written to disk, so the log ends with the app.
- Lines are cleaned as they arrive: colour codes stripped, the home directory replaced by `~` (as written, with forward slashes, and escaped as in a Python repr), anything past 2,000 characters cut. uvicorn's access lines for successful `GET`s are dropped, since the app polls the API; failed requests and writes stay.
- The renderer reads it through `window.surfsense.sessionLog.read()`. `session-log:read` answers only the app's own window. The dialog polls it every second while open, and follows the newest line unless the user has scrolled up.

## Reporting

- A description is required. Continue on GitHub opens the `bug.yml` form through the link allowlist ([egress](egress.md)), prefilling the title (`[bug]` and the description's first line) and What happened? (the description, the toast's error when opened from one, and the system details [About](about.md) copies).
- The log never goes in the link: Electron's `shell.openExternal` refuses a URL over 2,081 characters on Windows. It goes to the clipboard instead, cut to its newest 50,000 characters so the issue fits GitHub's 65,536-character body, and the form's Logs field asks for it to be pasted. With Include the session log off, nothing is copied.
- A description too long for the link, which in Japanese or Chinese takes a few hundred characters at nine URL characters each, moves to the clipboard with the log in a fenced block, for What happened?. The link then carries only the title.
- If the clipboard write fails, GitHub is not opened, since the user would paste whatever was copied before into a public issue.
- Which part? and What did you expect? are left to fill in on GitHub: a URL cannot prefill a dropdown, and the expected result is the reporter's to say.
- Error toasts go through `errorToast()`, sonner's `toast.error` with a Report issue action that opens the dialog carrying the toast's title and description.
- An unexpected sidecar exit raises one of those toasts, naming the affected
  user-facing feature. The report carries the sidecar's internal name and exit
  code; requested stops produce no crash event.
- The dialog is an app dialog, like the egress prompt: opened over another dialog, say from Help while Settings is open, it opens as that dialog's nested dialog. Its draft survives a close, and a move to another dialog.

## Known gaps

- The main process's own warnings, such as a preference file it could not read, still go to the terminal only.
