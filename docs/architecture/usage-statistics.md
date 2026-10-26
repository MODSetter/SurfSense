# Usage statistics

An opt-in report that tells SurfSense this install was used, and once a week how much, in ranges. In the install's first week every report carries those ranges, and one more report goes out each time setup reaches a new step. It is off until the user says yes, carries no identifier, and every value in it is an enum, a boolean or a fixed format. The user can read the exact next report, and the last one sent, before and after saying yes. The update check, which counts installs that check in each day, is in [updates](updates.md).

**Code:** [`surfsense_local/backend/modules/usage_statistics/`](../../surfsense_local/backend/modules/usage_statistics/), [`surfsense_local/frontend/src/features/privacy-choices/`](../../surfsense_local/frontend/src/features/privacy-choices/), [`surfsense_local/frontend/src/features/onboarding/privacy-step/`](../../surfsense_local/frontend/src/features/onboarding/privacy-step/), and in Electron main `electron/src/main/usage-statistics/`, `privacy-choices/` and `admin-policy/`
**Decisions:** [ADR 0070](../adr/0070-opt-in-id-less-update-checks-and-usage-statistics.md)
**Contract:** [contract 5](../contracts/05-desktop-telemetry.md)

```text
  first-run step ─┐            Settings › About / › Network
                  ▼                        │
      window.surfsense.privacy ◀───────────┘   (preload bridge)
                  │
            Electron main ── privacy.json, policy.json, DO_NOT_TRACK
                  │  only when opted in: at most one daily report a UTC day,
                  │  and in the first week a setup report at each new step
                  ├── GET 127.0.0.1:<port>/usage-statistics/summary?since=<7 days ago, or firstRunAt>
                  │        the API reads surfsense.db, the counts file and the machine
                  └── POST https://usage.surfsense.com/api/usage   (≤ 4 KB, no cookies)
```

## What is sent

One JSON body, schema 1, revision 1.1 ([contract 5](../contracts/05-desktop-telemetry.md), part B), sent as two kinds of report:

- **Daily** (`trigger: "daily"`): at most one accepted a UTC day. The first try is about two minutes after launch, then an hourly tick tries again, up to three tries a UTC day.
- **Setup** (`trigger: "setup"`): only in the install's first week, the seven days from `firstRunAt`. Electron main checks every five minutes and sends one when onboarding has reached a later step than the furthest step reported, in the order not started, model chosen, model ready, first source, first answer. The furthest step reported starts at not started, before any report is accepted, so not started never sends one, and `unknown` never does. The new step is recorded only once the report is accepted, so at most four setup reports are accepted per install. A try that fails has no cap of its own: the next check, five minutes later, tries again until the step is reported or the first week ends. Its flags are all false. Once accepted it becomes the last report sent that Settings shows, but it never counts as the day's report or uses one of the day's tries.

The website route that accepts revision 1.1 goes live before any app that sends it is released: the route before it answers 400 to `trigger` and `gpu_runtime`.

What a report carries:

- Always: the schema number, the app's version, its platform (`win32-x64` and the like), its OS (`windows-11`, `macos-15`, `linux`), the interface language (`en`, `ja`, `de` or `other`), the ISO week the app first ran, why it was sent (`trigger`), and three flags: the install's first daily report ever, its first this ISO week, its first this UTC month. A day's daily reports therefore count the reporting installs active that day, and the flags count weekly and monthly actives and installs reporting for the first time. Actives are counted only from events whose `trigger` is `daily` or absent: a 2.2.4 app sends none, the route records its reports as `daily`, and events recorded before revision 1.1 have no trigger at all. An install that opts in late sends its first report then, so its age is `install_week`, not the first flag.
- The week in ranges: Basic chat turns, Agentic turns, whether a local or a remote model answered, the documents in the library, Studio outputs, plugin tool calls, and the furthest onboarding step the library shows. In the first week every report carries it, counted since `firstRunAt`, so an install that stops in its first days still shows how far setup got. After that, only the first daily report of an ISO week carries it, for the past seven days.
- The machine in ranges: memory, the GPU's vendor and its memory, and `gpu_runtime`, whether the model runtime can use the graphics card. It rides on the first daily report, and in the first week again on each report while the last one sent had an `unknown` part; never after the first week. `privacy.json` keeps what was last sent, and the furthest step reported, so both rules hold across restarts.

Never documents, prompts, file names, model names, hosts, the license key or an ID. The request carries the outbound session's `User-Agent: SurfSense`, which names no version. The website route at `usage.surfsense.com` validates every key and value, stores one personless event per report with the country its host derives from the IP address, and never reads or stores the address or the user agent; the hosting provider's request logs keep both for a short time, as the privacy page says.

No identifier ties one install's reports together, but the values that never change for an install (its platform, OS, language and install week) together with the country can single out an install whose combination is uncommon, and the reports that carry hardware add it; so figures are read in aggregate, and no page may say reports cannot be told apart.

## Consent

- Privacy choices is onboarding's first step, right after the welcome, counted in its progress like the model steps: two rows, update checks and usage statistics, each with equal Yes and No buttons, neither chosen beforehand, and Continue only once both are answered. Continue calls `completeFirstRun`, which writes both answers and `firstRunAsked`. Each row says in one line what it does; the info icon beside its title shows the full description with every host its answer reaches, and the link below opens exactly what it sends.
- Onboarding always shows the step in the desktop app. An install that answered already (`firstRunAsked`), or that comes back from the first model step, sees its answers chosen. An install that finished onboarding never sees it; its usage statistics stay `null`, read as off, until the user turns them on. A bridge that cannot read its state skips the step, with both left off, rather than holding setup on an empty card.
- Settings › About has the Usage statistics switch beside App updates. Both say what they do as onboarding does, in the same one-line summary with the full description behind an info icon, and each has "Show exactly what's sent". For usage statistics that shows the next daily report as Electron main would build it now (`previewUsageReport`, not sent), the last report sent, daily or setup, and when, and the host. Settings › Network lists the same switch as a row with its host and its last call, which is that last report.
- Turning the switch off stops the next report; nothing already sent can be recalled, because no identifier marks which reports were this install's.

## Policy

Usage statistics are forced off, and the switch is locked with the reason shown, when:

- `DO_NOT_TRACK=1` or `SURFSENSE_NO_TELEMETRY=1` is set in the app's environment, or
- the admin policy file says `"usageStatistics": "off"`. Electron main reads it once at startup from `%ProgramData%/SurfSense/policy.json`, `/Library/Application Support/SurfSense/policy.json` or `/etc/surfsense/policy.json`. The same file can turn update checks off (`"updates": "off"`) or send them to a mirror (`"updateFeed"`).

A locked row is already answered in the first-run step. An unpackaged development build never reports unless `SURFSENSE_TELEMETRY_DEV_ENDPOINT` names a test server.

## The summary endpoint

`GET /usage-statistics/summary?since=<ISO time>` on the app's local API answers the report's `week`, `hardware` and `ui_language`, computed on each read and sent nowhere by the API itself. The API binds to loopback unless `SURFSENSE_LOCAL_HOST` names another address, and this route is exposed exactly as every other route then is. Electron main asks for it with `since` at `firstRunAt` in the install's first week and seven days back after it, and adds the rest. A missing or malformed `since` is a 422.

| Value | Read from |
|---|---|
| `chat_turns` | `chat_messages` rows with the user's role, since `since`, in threads that are not an agent's |
| `agent_turns` | the counts file: one per Agentic turn its engine took; a turn refused before it started is not one |
| `model_source` | the counts file: the kind of model that answered, counted once a Basic chat or Agentic reply ends with text. SurfSense's own llama.cpp is local; every connection is remote, even one on this machine |
| `sources` | `documents` of type file or note, now, whatever their age |
| `studio_outputs` | `artifacts` created since `since` |
| `plugin_calls` | the counts file: each `tools/call` in a request through the agent's plugin gateway |
| `onboarding` | the library as it stands: any reply with text, in a Basic chat row or the counts file, else any source, else a chat model chosen and ready (a connection, or SurfSense's own model on disk), else chosen, else not started. A turn whose model failed is not an answer |
| `hardware.ram_gb` | installed memory, read with `psutil` and bucketed by the size it was sold as |
| `hardware.gpu`, `vram_gb` | the device the local model catalog prices against, from the names ggml gives it; `none` and `0` when there is no GPU, `unknown` when the OS sees a card the runtime cannot reach |
| `ui_language` | the language picked in Settings › General, as Electron stores it, else the system's, resolved as Electron resolves it |

The counts file, `usage-counts.json` in the data folder, holds what leaves no row in `surfsense.db`: hourly counts of Agentic turns, plugin calls and local and remote answers, and whether a model has ever answered with text. It is pruned after 40 days and holds no content. A library that had chats before counting began has turns nobody counted, so for a window that starts before counting did, the three values it feeds are `unknown`, never `0`. No schema migration was needed.

## Tests

- [`tests/integration/usage_statistics/test_summary_route.py`](../../surfsense_local/backend/tests/integration/usage_statistics/test_summary_route.py) runs the route over a migrated library on a stated machine: a new install, a busy week, a window that began before counting, no counts file, the onboarding steps, and a bad `since`.
- [`tests/unit/usage_statistics/`](../../surfsense_local/backend/tests/unit/usage_statistics/) covers the buckets' edges, the hardware reading, the interface language and the counts file.
- The routes' counting runs in CI on stand-ins: a Basic chat reply and a failed turn on the stub encoder ([`tests/integration/chat/test_usage_counts.py`](../../surfsense_local/backend/tests/integration/chat/test_usage_counts.py)), an Agentic turn that answers and one that fails on the stand-in Claude Code ([`tests/integration/agent/claude_code/test_usage_counts.py`](../../surfsense_local/backend/tests/integration/agent/claude_code/test_usage_counts.py)), and plugin calls through the gateway.
- In the frontend, the privacy step's tests in [`onboarding-page.test.tsx`](../../surfsense_local/frontend/src/features/onboarding/onboarding-page.test.tsx), [`usage-statistics-settings.test.tsx`](../../surfsense_local/frontend/src/features/privacy-choices/usage-statistics-settings.test.tsx) and [`network-settings.test.tsx`](../../surfsense_local/frontend/src/features/egress/network-settings.test.tsx) drive a stub of the bridge.
- Electron main's reporter, policy reader, `privacy.json` and bridge each have a `*.test.ts` beside them.

## Known gaps

- The counts file is written by the API, so a turn whose request never reached it is not counted.
- An Agentic reply's kind of model is the text model selected when it ended, which the user could have changed during the turn.
- The opencode engine's count of an answer runs only where `pnpm build:opencode` staged opencode, so CI covers it through the Claude Code engine alone.
