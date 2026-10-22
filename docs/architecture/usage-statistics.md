# Usage statistics

An opt-in report that tells SurfSense this install was used, and once a week how much, in ranges. It is off until the user says yes, carries no identifier, and every value in it is an enum, a boolean or a fixed format. The user can read the exact next report, and the last one sent, before and after saying yes. The update check, which counts installs that check in each day, is in [updates](updates.md).

**Code:** [`surfsense_local/backend/modules/usage_statistics/`](../../surfsense_local/backend/modules/usage_statistics/), [`surfsense_local/frontend/src/features/privacy-choices/`](../../surfsense_local/frontend/src/features/privacy-choices/), [`surfsense_local/frontend/src/features/onboarding/privacy-step/`](../../surfsense_local/frontend/src/features/onboarding/privacy-step/), and in Electron main `electron/src/main/usage-statistics/`, `privacy-choices/` and `admin-policy/`
**Decisions:** [ADR 0068](../adr/0068-opt-in-id-less-update-checks-and-usage-statistics.md)
**Contract:** [contract 5](../contracts/05-desktop-telemetry.md)

```text
  first-run step ─┐            Settings › About / › Network
                  ▼                        │
      window.surfsense.privacy ◀───────────┘   (preload bridge)
                  │
            Electron main ── privacy.json, policy.json, DO_NOT_TRACK
                  │  at most once a UTC day, only when opted in
                  ├── GET 127.0.0.1:<port>/usage-statistics/summary?since=<7 days ago>
                  │        the API reads surfsense.db, the counts file and the machine
                  └── POST https://usage.surfsense.com/api/usage   (≤ 4 KB, no cookies)
```

## What is sent

One JSON body, schema 1, at most once per UTC day ([contract 5](../contracts/05-desktop-telemetry.md), part B):

- Always: the schema number, the app's version, its platform (`win32-x64` and the like), its OS (`windows-11`, `macos-15`, `linux`), the interface language (`en`, `ja`, `de` or `other`), the ISO week the app first ran, and three flags: the install's first report ever, its first this ISO week, its first this UTC month. A day's reports therefore count the installs active that day, and the flags count weekly and monthly actives and new installs, with nothing to join reports by.
- On the first report of an ISO week, the past seven days in ranges: Basic chat turns, Agentic turns, whether a local or a remote model answered, the documents in the library, Studio outputs, plugin tool calls, and the furthest onboarding step the library shows.
- On the first report ever, the machine in ranges: memory, the GPU's vendor and its memory.

Never documents, prompts, file names, model names, hosts, the license key or an ID. The website route at `usage.surfsense.com` validates every key and value, stores one personless event per report with the country its host derives from the IP address, and never reads or stores the address or the user agent.

## Consent

- A new install answers in the Privacy choices step, right after the welcome in onboarding: two rows, update checks and usage statistics, each with equal Yes and No buttons, neither chosen beforehand, and Continue only once both are answered. Continue calls `completeFirstRun`, which writes both answers and `firstRunAsked`. Each row opens exactly what it sends.
- An install that finished onboarding never sees the step, and one that answered (`firstRunAsked`) skips it. Its usage statistics stay `null`, read as off, until the user turns them on.
- Settings › About has the Usage statistics switch beside App updates, with "Show exactly what's sent": the next report as Electron main would build it now (`previewUsageReport`, not sent), the last report sent and when, and the host. Settings › Network lists the same switch as a row with its host and its last call.
- Turning the switch off stops the next report; nothing already sent can be recalled, because nothing ties it to this install.

## Policy

Usage statistics are forced off, and the switch is locked with the reason shown, when:

- `DO_NOT_TRACK=1` or `SURFSENSE_NO_TELEMETRY=1` is set in the app's environment, or
- the admin policy file says `"usageStatistics": "off"`. Electron main reads it once at startup from `%ProgramData%/SurfSense/policy.json`, `/Library/Application Support/SurfSense/policy.json` or `/etc/surfsense/policy.json`. The same file can turn update checks off (`"updates": "off"`) or send them to a mirror (`"updateFeed"`).

A locked row is already answered in the first-run step. An unpackaged development build never reports unless `SURFSENSE_TELEMETRY_DEV_ENDPOINT` names a test server.

## The summary endpoint

`GET /usage-statistics/summary?since=<ISO time>` on the app's loopback API answers the report's `week`, `hardware` and `ui_language`, computed on each read and sent nowhere by the API itself. Electron main asks for it with `since` seven days back and adds the rest. A missing or malformed `since` is a 422.

| Value | Read from |
|---|---|
| `chat_turns` | `chat_messages` rows with the user's role, since `since`, in threads that are not an agent's |
| `agent_turns` | the counts file: one per Agentic turn sent |
| `model_source` | the counts file: the kind of model asked to answer each turn. SurfSense's own llama.cpp is local; every connection is remote, even one on this machine |
| `sources` | `documents` of type file or note, now, whatever their age |
| `studio_outputs` | `artifacts` created since `since` |
| `plugin_calls` | the counts file: each `tools/call` in a request through the agent's plugin gateway |
| `onboarding` | the library as it stands: any answer, else any source, else a chat model chosen and ready (a connection, or SurfSense's own model on disk), else chosen, else not started |
| `hardware.ram_gb` | installed memory, read with `psutil` and bucketed by the size it was sold as |
| `hardware.gpu`, `vram_gb` | the device the local model catalog prices against, from the names ggml gives it; `none` and `0` when there is no GPU, `unknown` when the OS sees a card the runtime cannot reach |
| `ui_language` | the language picked in Settings › General, as Electron stores it, else the system's, resolved as Electron resolves it |

The counts file, `usage-counts.json` in the data folder, holds what leaves no row in `surfsense.db`: hourly counts of Agentic turns, plugin calls and local and remote answers, and whether a model has ever answered. It is pruned after 40 days and holds no content. A library that had chats before counting began has turns nobody counted, so for a window that starts before counting did, the three values it feeds are `unknown`, never `0`. No schema migration was needed.

## Tests

- [`tests/integration/usage_statistics/test_summary_route.py`](../../surfsense_local/backend/tests/integration/usage_statistics/test_summary_route.py) runs the route over a migrated library on a stated machine: a new install, a busy week, a window that began before counting, no counts file, the onboarding steps, and a bad `since`.
- [`tests/unit/usage_statistics/`](../../surfsense_local/backend/tests/unit/usage_statistics/) covers the buckets' edges, the hardware reading, the interface language and the counts file.
- In the frontend, the privacy step's tests in [`onboarding-page.test.tsx`](../../surfsense_local/frontend/src/features/onboarding/onboarding-page.test.tsx), [`usage-statistics-settings.test.tsx`](../../surfsense_local/frontend/src/features/privacy-choices/usage-statistics-settings.test.tsx) and [`network-settings.test.tsx`](../../surfsense_local/frontend/src/features/egress/network-settings.test.tsx) drive a stub of the bridge.
- Electron main's reporter, policy reader, `privacy.json` and bridge each have a `*.test.ts` beside them.

## Known gaps

- The counts file is written by the API, so a turn whose request never reached it is not counted.
- `model_source` records the kind of model selected when a turn was sent, not whether it then answered.
