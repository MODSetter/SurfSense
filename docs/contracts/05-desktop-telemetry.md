# Contract 5: desktop telemetry

What the desktop app may send about itself, and only with the user's yes: at most one automatic update check per UTC day, plus the checks the user starts, and an opt-in usage report. Version 1, revision 1.2 (29 Oct 2026). Revision 1.1 adds the first week's setup reports, the report's `trigger` and `hardware.gpu_runtime`. Revision 1.2 adds `install_age`, `active.age` and the week's `days_used_7` and `days_used_28`, so retention and how often an install is used read by cohort with no ID. The schema number stays 1 and every addition is optional, so a 2.2.4 or 2.2.5 app's reports stay valid. The reverse does not hold: the route before revision 1.1 answers 400 to `trigger`, `gpu_runtime`, and `week` or `hardware` outside its flags, and the route before revision 1.2 answers 400 to `install_age`, `active.age` and `days_used_*`, so the `/api/usage` route that accepts a revision is deployed to `usage.surfsense.com` before any app that sends it is released. It binds four parts that ship apart: the Electron main process, the app's UI, the app's local API, and the website routes at `updates.surfsense.com` and `usage.surfsense.com`. Why the app sends anything at all is [ADR 0070](../adr/0070-opt-in-id-less-update-checks-and-usage-statistics.md); how the app does it is [usage statistics](../architecture/usage-statistics.md) and [updates](../architecture/updates.md).

No part of this contract carries an identifier. Not `x-user-staging-id`, not a licence key, not an install ID, not a cookie, anywhere.

## A. Update feed

### The app (Electron main)

- electron-updater runs with a custom provider. The feed base is `https://updates.surfsense.com/api/updates/`; an admin policy's `updateFeed` (part C) may replace it with an `https` mirror.
- It requests `GET <base><channelFile>`, where `channelFile` is `stable.yml` (Windows), `stable-mac.yml` (macOS), `stable-linux.yml` (Linux x64) or `stable-linux-arm64.yml` (Linux arm64).
- That one request, and no other, carries these headers:

  | Header | Value |
  |---|---|
  | `X-SurfSense-Version` | the app's semver |
  | `X-SurfSense-Platform` | one of `win32-x64`, `win32-arm64`, `darwin-arm64`, `darwin-x64`, `linux-x64`, `linux-arm64` |
  | `X-SurfSense-OS` | one of `windows-10`, `windows-11`, `macos-<major number>`, `linux` |

- Timeout 10 s. On **any** failure of our feed (a network error, the timeout, a status other than 200, a body that is not a valid manifest, a missing version, or any file URL that is not exactly `https://github.com/MODSetter/SurfSense/releases/download/v<version>/<file name>`), the provider fetches `https://github.com/MODSetter/SurfSense/releases/latest/download/<channelFile>` directly, with no SurfSense header and no staging ID, and uses that, resolving a relative file name to `https://github.com/MODSetter/SurfSense/releases/download/v<version>/<name>`. Only when GitHub fails too does the check fail.
- **Updates are never blocked because `updates.surfsense.com` is down, slow or wrong.** The one exception: with an admin policy's `updateFeed` mirror there is no GitHub fallback, because such sites reach nothing else.

### The website route (`www`, served at `updates.surfsense.com`)

- `GET /api/updates/<file>`. `file` must match `^stable(-mac|-linux(-arm64)?)?\.yml$`; anything else, `latest*.yml` included, answers 404.
- It fetches `https://github.com/MODSetter/SurfSense/releases/latest/download/<file>`, following redirects, revalidated every 900 s.
- It requires a `version: x.y.z` line, and every `url:` and `path:` value to be a bare file name matching `^SurfSense[-A-Za-z0-9._]*\.(exe|zip|dmg|AppImage|deb|rpm)$`, or already the exact absolute GitHub prefix for that version. It rewrites each to `https://github.com/MODSetter/SurfSense/releases/download/v<version>/<name>` and leaves `sha512`, `size`, `releaseDate` and `stagingPercentage` untouched.
- Success is 200 with `Content-Type: text/yaml` and `Cache-Control: no-store`. Any upstream or validation problem is 502, and the app then falls back to GitHub.
- It records one personless event, `desktop_update_check`, with `file`, `app_version` (the semver, or `"invalid"`), `platform` (the enum, or `"other"`), `os` (the enum, or `"other"`) and `country` (from `x-vercel-ip-country`, else `"unknown"`).
- It never reads, logs or stores the IP address or the User-Agent.

## B. Usage statistics (opt-in, unticked)

### The app (Electron main)

- `POST https://usage.surfsense.com/api/usage` with `Content-Type: application/json`, a body of at most 4 KB, a 10 s timeout, no cookies and no redirect followed. Both kinds of report below use this one request.
- Only when the user opted in and neither the policy nor `DO_NOT_TRACK` forbids it, and never from an unpackaged development build, unless `SURFSENSE_TELEMETRY_DEV_ENDPOINT` names somewhere to send it.
- An install's **first week** runs from `firstRunAt` to `firstRunAt` plus 7 days.
- **The daily report** (`"trigger": "daily"`): at most one accepted per UTC day, and up to 3 attempts per UTC day. Once accepted it sets `lastReport` and `lastSent`.
- **The setup report** (`"trigger": "setup"`), revision 1.1: only in the first week, checked every 5 minutes, never after it. The furthest step reported starts at `not_started`, before any report is accepted, so `not_started` never sends one. A setup report is sent when the local summary's `week.onboarding` is a later step than the furthest step reported, in the order `not_started` < `model_chosen` < `model_ready` < `first_source` < `first_answer`; `unknown` never sends one. It carries `week`, and its `active` flags are all false. Once accepted it sets `lastSent`, `at` and `body`, as a daily report does, but never `lastReport` or the day's attempts. The new furthest step is recorded only once the POST is accepted, so at most four setup reports are accepted per install. A try that is not accepted (a network error, the timeout, a 5xx) is tried again at a later check, at most three tries per step per UTC day and an hour apart; a 4xx answer ends that step's tries until the next UTC day, since the same body would be refused again. The budget is kept in `privacy.json` (`setupTries`), so a restart does not reset it. Once `first_answer` is reported, the checks read nothing more. Every accepted report, daily or setup, raises the furthest step reported.
- **`week`**: on every report in the first week, covering the time since `firstRunAt`; after it, only on a daily report whose `active.week` is true, covering the 7 days before it. From revision 1.2 its `days_used_7` and `days_used_28` count, of the 7 and 28 whole UTC days before the report's day, the days that show use; the report's own day is never counted, so a report sent minutes after launch reads the same as one sent at night.
- **`install_age`**, revision 1.2: on every report, daily or setup, the whole UTC days from `firstRunAt`'s day to the report's day, in ranges. `active.age` is true on the first daily report in its range, and false on a setup report.
- **`hardware`**: on the first daily report; and, in the first week only, on any later report while the last hardware sent had `gpu`, `vram_gb` or `gpu_runtime` equal to `unknown`, and only when the block differs from the one last sent (a card the runtime cannot reach keeps `vram_gb` unknown all week, so an unchanged block is not repeated). Never resent after the first week.

The body, schema 1. Every value is an enum, a boolean or a fixed format, never free text:

```json
{
  "schema": 1,
  "app_version": "2.2.5",
  "platform": "win32-x64",
  "os": "windows-11",
  "ui_language": "en",
  "install_week": "2026-W43",
  "install_age": "8-14",
  "trigger": "daily",
  "active": { "first": false, "week": true, "month": false, "age": true },
  "hardware": null,
  "week": {
    "chat_turns": "10-49",
    "agent_turns": "0",
    "model_source": "local",
    "sources": "10-99",
    "studio_outputs": "1-4",
    "plugin_calls": "0",
    "onboarding": "first_answer",
    "days_used_7": "2-3",
    "days_used_28": "4-7"
  }
}
```

A setup report in the first week, on a machine whose card the model runtime cannot reach, so its hardware rides again:

```json
{
  "schema": 1,
  "app_version": "2.2.5",
  "platform": "win32-x64",
  "os": "windows-11",
  "ui_language": "en",
  "install_week": "2026-W44",
  "install_age": "1",
  "trigger": "setup",
  "active": { "first": false, "week": false, "month": false, "age": false },
  "hardware": { "ram_gb": "16-31", "gpu": "amd", "vram_gb": "unknown", "gpu_runtime": "unreachable" },
  "week": {
    "chat_turns": "0",
    "agent_turns": "0",
    "model_source": "none",
    "sources": "0",
    "studio_outputs": "0",
    "plugin_calls": "0",
    "onboarding": "model_ready",
    "days_used_7": "1",
    "days_used_28": "1"
  }
}
```

| Field | Values | Meaning |
|---|---|---|
| `platform` | as `X-SurfSense-Platform` | |
| `os` | as `X-SurfSense-OS` | |
| `ui_language` | `en`, `ja`, `de`, `other` | the interface's language |
| `install_week` | `YYYY-Www` | the ISO week of `firstRunAt`, stored locally |
| `install_age` | `0`, `1`, `2-3`, `4-7`, `8-14`, `15-30`, `31-60`, `61+`; optional, revision 1.2 | whole UTC days from `firstRunAt`'s day to the report's day |
| `trigger` | `daily`, `setup`; optional, revision 1.1 | why the report was sent: the day's report, or setup reaching a new step in the first week. A 2.2.4 app leaves it out, which means `daily` |
| `active.first` | boolean | the first daily report ever; false on a setup report |
| `active.week` | boolean | the first daily report this ISO week; false on a setup report |
| `active.month` | boolean | the first daily report this UTC calendar month; false on a setup report |
| `active.age` | boolean; optional, revision 1.2 | the first daily report in this `install_age` range; false on a setup report |
| `hardware` | `null`, or the object below | on the first daily report, and in the first week when it changed while the last hardware sent had an `unknown` part |
| `hardware.ram_gb` | `<8`, `8-15`, `16-31`, `32-63`, `64+` | |
| `hardware.gpu` | `nvidia`, `amd`, `intel`, `apple`, `none`, `unknown` | |
| `hardware.vram_gb` | `0`, `<4`, `4-7`, `8-11`, `12-23`, `24+`, `unknown` | |
| `hardware.gpu_runtime` | `reachable`, `unreachable`, `none`, `unknown`; optional, revision 1.1 | whether the model runtime can use the graphics card: it can, the OS sees a card the runtime cannot reach, there is no card, or nobody knows |
| `week` | `null`, or the object below | on every report in the first week, covering the time since `firstRunAt`; after it, only when `active.week` is true, covering the 7 days before the report |
| `week.chat_turns` | `0`, `1-9`, `10-49`, `50+`, `unknown` | the user's turns in Basic chat |
| `week.agent_turns` | `0`, `1-9`, `10-49`, `50+`, `unknown` | Agentic turns |
| `week.model_source` | `none`, `local`, `remote`, `both`, `unknown` | which kinds of model answered in the window |
| `week.sources` | `0`, `1-9`, `10-99`, `100-999`, `1000+`, `unknown` | documents in the library now |
| `week.studio_outputs` | `0`, `1-4`, `5+`, `unknown` | Studio outputs created in the window |
| `week.plugin_calls` | `0`, `1-9`, `10+`, `unknown` | plugin tool calls in the window |
| `week.onboarding` | `not_started`, `model_chosen`, `model_ready`, `first_source`, `first_answer`, `unknown` | the furthest step ever reached |
| `week.days_used_7` | `0`, `1`, `2-3`, `4-6`, `7`, `unknown`; optional, revision 1.2 | of the 7 whole UTC days before the report's day, the days with a Basic chat turn, a document added to the library, a Studio output, or an Agentic turn, answer or plugin call |
| `week.days_used_28` | `0`, `1`, `2-3`, `4-7`, `8-14`, `15-28`, `unknown`; optional, revision 1.2 | the same, over the 28 days before the report's day |

### The website route (`www`, served at `usage.surfsense.com`)

- `POST /api/usage`, validated strictly: an unknown key or value answers 400, a body over 4 KB 413, a wrong content type 415. Success is 204. `trigger`, `hardware.gpu_runtime`, and revision 1.2's `install_age`, `active.age`, `week.days_used_7` and `week.days_used_28` may be absent, and `week` and `hardware` are accepted on any report; when each rides is the app's rule above, not the route's.
- It records one personless event, `desktop_usage_report`, with the fields flattened (`app_version`, `platform`, `os`, `ui_language`, `install_week`, `install_age`, `trigger`, `active_first`, `active_week`, `active_month`, `active_age`, `hardware_ram_gb`, `hardware_gpu`, `hardware_vram_gb`, `hardware_gpu_runtime`, `week_chat_turns`, `week_agent_turns`, `week_model_source`, `week_sources`, `week_studio_outputs`, `week_plugin_calls`, `week_onboarding`, `week_days_used_7`, `week_days_used_28`) plus `country` from `x-vercel-ip-country`. `trigger` is `daily` when the report left it out; a field the report did not send adds no property.
- It never reads, logs or stores the IP address or the User-Agent.

### Reading the events

- Daily, weekly and monthly actives, and first reports, are counted only from events whose `trigger` is `daily` or absent; events recorded before revision 1.1 have none. A setup report's flags are all false, and it is not a day's activity.
- Retention by cohort, from revision 1.2: a cohort is the reports of one `install_week`. Its size is the daily reports with `active_first` true. Those with `active_age` true and a given `install_age` count the cohort's installs used at least once in that range: day 1 from `1`, the rest of the first week from `2-3` and `4-7`, then `8-14`, `15-30`, `31-60` and `61+`. Weekly retention is the reports with `active_week` true per `install_week`, by the ISO week they were sent. An install that opts in late starts at its `install_age` then, so a cohort's later ranges can exceed its first.
- How often installs are used, from revision 1.2: `week_days_used_7` and `week_days_used_28` are read from daily reports with `active_week` true, one per install per ISO week, so a busy install is not counted on each of its days. In the first week they cover only the days since installation.
- `firstRunAt` is stamped on the first launch of 2.2.4 or later, so an install updated from an earlier version reads as installed then, in `install_week` and `install_age` alike.
- Events are counted, never joined: nothing ties one install's reports together.

## C. Local state, policy and the bridge (desktop only)

### State

`privacy.json` in Electron's userData:

```json
{
  "usageStatistics": null,
  "firstRunAt": "2026-10-22T09:00:00.000Z",
  "firstRunAsked": false,
  "lastReport": null,
  "lastSent": null
}
```

| Field | Values |
|---|---|
| `usageStatistics` | `true`, `false`, or `null` for never asked |
| `firstRunAt` | ISO time |
| `firstRunAsked` | boolean |
| `lastReport` | `{ "day": "YYYY-MM-DD", "week": "YYYY-Www", "month": "YYYY-MM" }` or `null`: the periods of the last accepted daily report |
| `lastSent` | `{ "at": ISO time, "body": object }` or `null`: the last accepted report, daily or setup |

From revision 1.1 it also keeps the furthest onboarding step an accepted report carried and what the last hardware sent held, so the setup report and the hardware rule of part B hold across restarts. Neither is ever sent. Revision 1.2 keeps nothing new: `active.age` compares the `install_age` of `lastReport.day` with today's.

The existing `updates.json` keeps `automatic` and `lastCheckedAt`.

### Policy

- `DO_NOT_TRACK=1` or `SURFSENSE_NO_TELEMETRY=1` in the environment forces usage statistics off.
- A JSON policy file, read once at startup from `%ProgramData%/SurfSense/policy.json` (Windows), `/Library/Application Support/SurfSense/policy.json` (macOS) or `/etc/surfsense/policy.json` (Linux), may hold `"updates": "off" | "user"`, `"usageStatistics": "off" | "user"` and `"updateFeed": "<https url>"`.
- A setting the policy forces is locked in the UI.
- An install a package manager owns turns update checks off and locks them, with `lockedReason: "channel"` and `channel` naming it: `scoop`, `aur`, `snap`, `flatpak`, `nix` or `apt`. Electron main never checks for such an install, so nothing in part A is sent. When the policy also turns updates off, the policy is the reason and `channel` is `null`.

### The bridge

`window.surfsense.privacy`, from the preload script:

```ts
getState(): Promise<{
  updates: {
    automatic: boolean
    locked: boolean
    lockedReason: "policy" | "channel" | null
    channel: "scoop" | "aur" | "snap" | "flatpak" | "nix" | "apt" | null // only when lockedReason is "channel"
    host: string
    fallbackHost: "github.com" | null
    lastCheckedAt: string | null
    lastRequest: { url: string; headers: Record<string, string> } | null
  }
  usageStatistics: {
    enabled: boolean | null
    locked: boolean
    lockedReason: "policy" | "do_not_track" | null
    host: string
    lastSent: { at: string; body: object } | null
  }
  firstRunAsked: boolean
}>
setUsageStatistics(enabled: boolean): Promise<void>
setUpdatesAutomatic(enabled: boolean): Promise<void>
previewUsageReport(): Promise<object> // the exact next daily body, built but not sent
completeFirstRun(choices: { updates: boolean; usageStatistics: boolean }): Promise<void>
onStateChanged(listener): () => void
```

It reuses the existing `window.surfsense.updates` bridge rather than duplicating it: `setUpdatesAutomatic` is that bridge's switch.

`previewUsageReport()` always builds the daily body, in the first week too. A setup report is built from the same summary, with `trigger: "setup"`, its `active` flags false and `hardware` by part B's rule, and Settings shows it as `lastSent` once it is accepted.

### The local summary

`GET http://127.0.0.1:<api port>/usage-statistics/summary?since=<ISO time>` answers:

```json
{
  "week": { "chat_turns": "10-49", "agent_turns": "0", "model_source": "local", "sources": "10-99", "studio_outputs": "1-4", "plugin_calls": "0", "onboarding": "first_answer", "days_used_7": "2-3", "days_used_28": "4-7" },
  "hardware": { "ram_gb": "16-31", "gpu": "nvidia", "vram_gb": "8-11", "gpu_runtime": "reachable" },
  "ui_language": "en"
}
```

with the values of part B, computed at read time from `surfsense.db` and the runtime. Electron main asks with `since` at `firstRunAt` in the first week and 7 days back after it, and adds `schema`, `app_version`, `platform`, `os`, `install_week`, `install_age`, `trigger` and `active`.

From revision 1.1, `hardware.gpu_runtime` is the runtime's view of the graphics card: `reachable` when the model runtime can use it, `unreachable` when the operating system sees a card the runtime cannot reach, `none` when there is no card, and `unknown` when the runtime's view cannot be read. With `unreachable`, `gpu` is the vendor in the operating system's adapter names and `vram_gb` is `unknown`.

From revision 1.2, `week.days_used_7` and `days_used_28` are counted from the request's UTC day, whatever `since` is: the days before it with a `chat_messages` row of the user's role, a file or note `documents` row or an `artifacts` row created on them, or any count in an hour of the counts file. They are `unknown` when the counts file is missing or began after the window's first day, as `agent_turns` is.

## As first built

Details the first implementation settled, within the contract:

- `getState()` answers `null` to anything but the app's own window, and `previewUsageReport()` answers `null` on a machine whose platform or OS has no label above, which then sends no report.
- `privacy.json` also keeps `attempts`, `{ "day", "count" }`, so the three attempts a day hold across restarts. It is never sent.
- The summary's `hardware` is `null` when the machine's memory cannot be read; Electron main then buckets `os.totalmem()` itself and reports the GPU and its memory as `unknown`. Electron main reads the summary with a 5 s timeout, and a summary it cannot read leaves every `week` value `unknown`.
- Electron main asks GitHub with a 30 s timeout, longer than the 10 s on our feed, since it is the last resort, and refuses a redirect from our feed so the headers never reach another host.
- `lastRequest` is the last request to `host` since the app started; it is kept in memory only.
- A packaged app reads its channel once at startup, first match wins: a `resources/install-channel` file holding one of the six ids, which a repackager writes (Scoop, an AUR PKGBUILD, a Nix derivation); then, on Linux only, SurfSense's own snap (`snap`: `SNAP_NAME` is `surfsense-local` and the executable is under `$SNAP`, so another snap's variables inherited by a normal install do not count), `FLATPAK_ID` set or `/.flatpak-info` present (`flatpak`), an executable under `/nix/store/` (`nix`), and `resources/package-type` reading `deb` while `/etc/apt/sources.list.d/surfsense.list` exists (`apt`). Anything unreadable counts as no channel.

## Tests each side owns

- The app's local API (`surfsense_local/backend`): `tests/integration/usage_statistics/test_summary_route.py` and `tests/unit/usage_statistics/` for the summary's buckets, hardware, language and counts.
- The app's UI (`surfsense_local/frontend`): the privacy step in `src/features/onboarding/onboarding-page.test.tsx`, `src/features/privacy-choices/usage-statistics-settings.test.tsx` and `src/features/egress/network-settings.test.tsx`.
- Electron main (`surfsense_local/electron`): the feed provider, the usage reporter, the policy reader, the install-channel detector, `privacy.json` and the bridge's IPC, each in a `*.test.ts` beside its module.
- The website routes (`www`): validation, rewriting and the 404, 502, 400, 413 and 415 answers of both routes.
