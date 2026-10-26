# ADR 0070: The app may send opt-in, ID-less update checks and usage statistics

- **Status:** Accepted
- **Date:** 2026-10-21
- **Supersedes:** [ADR 0016](0016-no-telemetry.md); amends [ADR 0017](0017-egress-off-by-default.md), [ADR 0020](0020-two-update-channels.md) and [ADR 0060](0060-one-consent-question-per-user-action.md)

## Context

[ADR 0016](0016-no-telemetry.md) ruled out telemetry, so the maintainers could not tell how many installs exist, which versions and platforms they run, whether a new user gets past setup, or what hardware the model ladder has to fit. Decisions about models, packaging and installer size were made blind. Meanwhile an allowed update check already reached github.com, and until 2.2.3 electron-updater sent it a persistent install ID: GitHub could count installs, SurfSense could not, and the one identifier on the wire was the one nobody chose.

The constraints stand: the app is sold as private and offline-first, every outbound call needs the user's yes ([ADR 0017](0017-egress-off-by-default.md)), and a business site must be able to turn everything off. Updates are a safety path, so a SurfSense host must never be able to block one.

## Decision

- **Update checks.** Once the user allows them, the app checks at most once a UTC day, and whenever the user clicks Check now. The manifest request goes to `updates.surfsense.com` with three headers, the app's version, its platform and its OS, and no ID ([contract 5](../contracts/05-desktop-telemetry.md), part A). Any failure of that host, slow or wrong included, falls back to GitHub directly, without the headers. Installers download from GitHub, or from the mirror when an admin policy names one. The host records one personless event per request, with the country its edge derives from the IP address, and never stores the address or the user agent; its provider's request logs keep both briefly. Counting the day's automatic checks approximates the installs that were open that day, with nothing extra on the wire; a check that read no manifest is tried again, so a day with failures can add a second event from one install.
- **Usage statistics.** A separate choice, off unless the user turns it on. At most one report a UTC day goes to `usage.surfsense.com`: whether this is the install's first report, its first this week and its first this month; once a week, counts in ranges from the past seven days; on the first report, the machine's memory, GPU vendor and graphics memory in ranges. Every value is an enum, a boolean or a fixed format (contract 5, part B). Never documents, prompts, file names, model names, hosts, the license key or an ID.
- **Consent.** A new install asks both questions in a Privacy choices step right after the welcome: two rows, neither preselected, equal Yes and No buttons, and Continue only once both are answered. An install that finished onboarding before this decision is not asked: its update setting stays as it was, and usage statistics stay off until the user turns them on in Settings.
- **Withdrawal and policy.** Either can be switched off in Settings › About or Settings › Network. `DO_NOT_TRACK=1` or `SURFSENSE_NO_TELEMETRY=1` forces usage statistics off. An admin policy file can turn either off or send update checks to a mirror, which has no GitHub fallback, and the UI shows the setting as locked (contract 5, part C).
- **Showing it.** Settings shows the exact next report, built but not sent, the last one sent and when, and the last update request with its URL and headers.
- **What stays from ADR 0016.** No crash reporting, no analytics SDK, no identifier of any kind. Support still runs on logs the user sends.

## Consequences

- With update checks on, SurfSense can count installs that checked in each day, with their versions, platforms and countries. With usage statistics on, it also receives the weekly counts above. Installs that said no, air-gapped sites and policy-locked machines are invisible, so any figure is reported with its coverage, never as a total.
- No identifier ties reports together, but an install's fixed values (platform, OS, language, install week) and its country can single out one whose combination is uncommon. Figures are read in aggregate, and the privacy page says so rather than claiming reports cannot be told apart.
- Two SurfSense hosts join the places the app can reach. The privacy page, [egress](../architecture/egress.md), [updates](../architecture/updates.md) and [usage statistics](../architecture/usage-statistics.md) list them with exactly what each receives.
- `updates.surfsense.com` sits on the update path but cannot block it. A policy mirror takes it off the path entirely.
- [ADR 0017](0017-egress-off-by-default.md) is amended: update checks and usage statistics are preferences Electron main holds, not `egress_destinations` rows, because Electron main makes both calls, and they are asked about in the first-run step rather than on a refused call. Settings › Network still lists both and switches both.
- [ADR 0020](0020-two-update-channels.md) is amended: the 2.x app reads its `stable` manifest through `updates.surfsense.com`'s route, which rewrites each file to its GitHub release URL, with GitHub's own `latest/download` behind it; the automatic check runs once a UTC day rather than at each launch. Updates stay off until the user says yes.
- [ADR 0060](0060-one-consent-question-per-user-action.md) is amended: on a new install, finishing the first-run step is the user action these two questions belong to, and each names every host its answer reaches, the fallback included.
- The weekly counts that leave no row in `surfsense.db` (Agentic turns, plugin calls, which kind of model answered) are kept as hourly counts in a small file in the data folder, pruned after 40 days, so the summary can be computed at read time without a schema migration.

## Where the code stands

The decision lands in three pull requests: the app's UI and local summary endpoint, the Electron main process (the feed provider, the reporter, the policy reader and the bridge), and the two website routes. Until all three are merged, a build holds only part of it.

- 27 Oct 2026: the first report went out about two minutes after launch, so its week showed no chats and onboarding not started, and the next week waited for the next ISO week: an install that stopped in its first week never showed how far setup got. A card the model runtime could not reach was reported as an `unknown` GPU, on the only report that carries hardware. [Contract 5](../contracts/05-desktop-telemetry.md) revision 1.1, schema still 1, changes the install's first week only: every report carries the week's counts, a setup report (`trigger: "setup"`) goes out each time setup reaches a new step, at most four accepted, and hardware is sent again while part of it is `unknown`, with `gpu_runtime` saying whether the runtime can use the card. Settings' next report is the next daily one, and its last report sent may be a setup report. The route that accepts revision 1.1 is deployed before an app that sends it is released. Daily actives are counted only from reports whose `trigger` is `daily` or absent ([usage statistics](../architecture/usage-statistics.md#what-is-sent)).
