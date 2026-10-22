# Contract 5: desktop telemetry

What the desktop app may send about itself, and only with the user's yes: at most one automatic update check per UTC day, plus the checks the user starts, and an opt-in usage report. Version 1. It binds four parts that ship apart: the Electron main process, the app's UI, the app's local API, and the website routes at `updates.surfsense.com` and `usage.surfsense.com`. Why the app sends anything at all is [ADR 0070](../adr/0070-opt-in-id-less-update-checks-and-usage-statistics.md); how the app does it is [usage statistics](../architecture/usage-statistics.md) and [updates](../architecture/updates.md).

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

### The website route (`surfsense_web`, served at `updates.surfsense.com`)

- `GET /api/updates/<file>`. `file` must match `^stable(-mac|-linux(-arm64)?)?\.yml$`; anything else, `latest*.yml` included, answers 404.
- It fetches `https://github.com/MODSetter/SurfSense/releases/latest/download/<file>`, following redirects, revalidated every 900 s.
- It requires a `version: x.y.z` line, and every `url:` and `path:` value to be a bare file name matching `^SurfSense[-A-Za-z0-9._]*\.(exe|zip|dmg|AppImage|deb)$`, or already the exact absolute GitHub prefix for that version. It rewrites each to `https://github.com/MODSetter/SurfSense/releases/download/v<version>/<name>` and leaves `sha512`, `size`, `releaseDate` and `stagingPercentage` untouched.
- Success is 200 with `Content-Type: text/yaml` and `Cache-Control: no-store`. Any upstream or validation problem is 502, and the app then falls back to GitHub.
- It records one personless event, `desktop_update_check`, with `file`, `app_version` (the semver, or `"invalid"`), `platform` (the enum, or `"other"`), `os` (the enum, or `"other"`) and `country` (from `x-vercel-ip-country`, else `"unknown"`).
- It never reads, logs or stores the IP address or the User-Agent.

## B. Usage statistics (opt-in, unticked)

### The app (Electron main)

- `POST https://usage.surfsense.com/api/usage` with `Content-Type: application/json`, a body of at most 4 KB, a 10 s timeout and no cookies.
- At most one successful report per UTC day, and up to 3 attempts per UTC day, only when the user opted in and neither the policy nor `DO_NOT_TRACK` forbids it.
- Never from an unpackaged development build, unless `SURFSENSE_TELEMETRY_DEV_ENDPOINT` names somewhere to send it.

The body, schema 1. Every value is an enum, a boolean or a fixed format, never free text:

```json
{
  "schema": 1,
  "app_version": "2.2.4",
  "platform": "win32-x64",
  "os": "windows-11",
  "ui_language": "en",
  "install_week": "2026-W43",
  "active": { "first": false, "week": true, "month": false },
  "hardware": null,
  "week": {
    "chat_turns": "10-49",
    "agent_turns": "0",
    "model_source": "local",
    "sources": "10-99",
    "studio_outputs": "1-4",
    "plugin_calls": "0",
    "onboarding": "first_answer"
  }
}
```

| Field | Values | Meaning |
|---|---|---|
| `platform` | as `X-SurfSense-Platform` | |
| `os` | as `X-SurfSense-OS` | |
| `ui_language` | `en`, `ja`, `de`, `other` | the interface's language |
| `install_week` | `YYYY-Www` | the ISO week of `firstRunAt`, stored locally |
| `active.first` | boolean | the first report ever |
| `active.week` | boolean | the first report this ISO week |
| `active.month` | boolean | the first report this UTC calendar month |
| `hardware` | `null`, or the object below | only when `active.first` is true |
| `hardware.ram_gb` | `<8`, `8-15`, `16-31`, `32-63`, `64+` | |
| `hardware.gpu` | `nvidia`, `amd`, `intel`, `apple`, `none`, `unknown` | |
| `hardware.vram_gb` | `0`, `<4`, `4-7`, `8-11`, `12-23`, `24+`, `unknown` | |
| `week` | `null`, or the object below | only when `active.week` is true; covers the 7 days before the report |
| `week.chat_turns` | `0`, `1-9`, `10-49`, `50+`, `unknown` | the user's turns in Basic chat |
| `week.agent_turns` | `0`, `1-9`, `10-49`, `50+`, `unknown` | Agentic turns |
| `week.model_source` | `none`, `local`, `remote`, `both`, `unknown` | which kinds of model answered in the window |
| `week.sources` | `0`, `1-9`, `10-99`, `100-999`, `1000+`, `unknown` | documents in the library now |
| `week.studio_outputs` | `0`, `1-4`, `5+`, `unknown` | Studio outputs created in the window |
| `week.plugin_calls` | `0`, `1-9`, `10+`, `unknown` | plugin tool calls in the window |
| `week.onboarding` | `not_started`, `model_chosen`, `model_ready`, `first_source`, `first_answer`, `unknown` | the furthest step ever reached |

### The website route (`surfsense_web`, served at `usage.surfsense.com`)

- `POST /api/usage`, validated strictly: an unknown key or value answers 400, a body over 4 KB 413, a wrong content type 415. Success is 204.
- It records one personless event, `desktop_usage_report`, with the fields flattened (`app_version`, `platform`, `os`, `ui_language`, `install_week`, `active_first`, `active_week`, `active_month`, `hardware_ram_gb`, `hardware_gpu`, `hardware_vram_gb`, `week_chat_turns`, `week_agent_turns`, `week_model_source`, `week_sources`, `week_studio_outputs`, `week_plugin_calls`, `week_onboarding`) plus `country` from `x-vercel-ip-country`.
- It never reads, logs or stores the IP address or the User-Agent.

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
| `lastReport` | `{ "day": "YYYY-MM-DD", "week": "YYYY-Www", "month": "YYYY-MM" }` or `null` |
| `lastSent` | `{ "at": ISO time, "body": object }` or `null` |

The existing `updates.json` keeps `automatic` and `lastCheckedAt`.

### Policy

- `DO_NOT_TRACK=1` or `SURFSENSE_NO_TELEMETRY=1` in the environment forces usage statistics off.
- A JSON policy file, read once at startup from `%ProgramData%/SurfSense/policy.json` (Windows), `/Library/Application Support/SurfSense/policy.json` (macOS) or `/etc/surfsense/policy.json` (Linux), may hold `"updates": "off" | "user"`, `"usageStatistics": "off" | "user"` and `"updateFeed": "<https url>"`.
- A setting the policy forces is locked in the UI.

### The bridge

`window.surfsense.privacy`, from the preload script:

```ts
getState(): Promise<{
  updates: {
    automatic: boolean
    locked: boolean
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
previewUsageReport(): Promise<object> // the exact next body, built but not sent
completeFirstRun(choices: { updates: boolean; usageStatistics: boolean }): Promise<void>
onStateChanged(listener): () => void
```

It reuses the existing `window.surfsense.updates` bridge rather than duplicating it: `setUpdatesAutomatic` is that bridge's switch.

### The local summary

`GET http://127.0.0.1:<api port>/usage-statistics/summary?since=<ISO time>` answers:

```json
{
  "week": { "chat_turns": "10-49", "agent_turns": "0", "model_source": "local", "sources": "10-99", "studio_outputs": "1-4", "plugin_calls": "0", "onboarding": "first_answer" },
  "hardware": { "ram_gb": "16-31", "gpu": "nvidia", "vram_gb": "8-11" },
  "ui_language": "en"
}
```

with the values of part B, computed at read time from `surfsense.db` and the runtime. Electron main adds `schema`, `app_version`, `platform`, `os`, `install_week` and `active`.

## As first built

Details the first implementation settled, within the contract:

- `getState()` answers `null` to anything but the app's own window, and `previewUsageReport()` answers `null` on a machine whose platform or OS has no label above, which then sends no report.
- `privacy.json` also keeps `attempts`, `{ "day", "count" }`, so the three attempts a day hold across restarts. It is never sent.
- The summary's `hardware` is `null` when the machine's memory cannot be read; Electron main then buckets `os.totalmem()` itself and reports the GPU and its memory as `unknown`. Electron main reads the summary with a 5 s timeout, and a summary it cannot read leaves every `week` value `unknown`.
- Electron main asks GitHub with a 30 s timeout, longer than the 10 s on our feed, since it is the last resort, and refuses a redirect from our feed so the headers never reach another host.
- `lastRequest` is the last request to `host` since the app started; it is kept in memory only.

## Tests each side owns

- The app's local API (`surfsense_local/backend`): `tests/integration/usage_statistics/test_summary_route.py` and `tests/unit/usage_statistics/` for the summary's buckets, hardware, language and counts.
- The app's UI (`surfsense_local/frontend`): the privacy step in `src/features/onboarding/onboarding-page.test.tsx`, `src/features/privacy-choices/usage-statistics-settings.test.tsx` and `src/features/egress/network-settings.test.tsx`.
- Electron main (`surfsense_local/electron`): the feed provider, the usage reporter, the policy reader, `privacy.json` and the bridge's IPC, each in a `*.test.ts` beside its module.
- The website routes (`surfsense_web`): validation, rewriting and the 404, 502, 400, 413 and 415 answers of both routes.
