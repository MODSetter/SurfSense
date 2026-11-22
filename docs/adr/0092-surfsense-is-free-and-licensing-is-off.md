# ADR 0092: SurfSense is free; licensing is off, the job packs ship in the app under Apache-2.0, and web search has no default server

- **Status:** Accepted
- **Date:** 2026-11-21
- **Supersedes:** [ADR 0047](0047-premium-plugins-are-source-available.md), [ADR 0067](0067-b2b-jobs-ship-as-paid-plugins.md), [ADR 0080](0080-surfsense-sells-one-business-license-priced-per-person.md) and [ADR 0082](0082-the-license-server-delivers-job-packs-from-private-releases.md); in part [ADR 0054](0054-surfsenses-plugins-run-on-one-plugin-host.md), its paid plugins and their licence check, and [ADR 0081](0081-surfsenses-scrapers-retire-and-web-pages-and-search-stay-free.md), web search going to SurfSense's own SearXNG server
- **Source:** maintainer decisions, 21 Nov 2026 (no permalink)

## Context

SurfSense Inc. winds down on 27 Nov 2026. The app stays, free indefinitely, as the maintainer's own project. Nothing runs on a server after that day except the website on Vercel: `api.surfsense.com` (the licence server and job-pack delivery), `plugins.surfsense.com` (the plugin host) and `searxng.surfsense.com` go away with the company's Azure account. The website serves the plugin registry's and OAuth sign-in's static files under `plugins.surfsense.com`, so installed apps keep those two.

Until now a Business licence unlocked the jobs ([ADR 0080](0080-surfsense-sells-one-business-license-priced-per-person.md)), the licence server delivered their packs from a private repository ([ADR 0082](0082-the-license-server-delivers-job-packs-from-private-releases.md)), and the paid plugins' code was under the Business Source License ([ADR 0047](0047-premium-plugins-are-source-available.md)). With no server and no company, a licence can be neither sold nor renewed, and a pack can no longer be downloaded. The company agreed in writing that all BSL code and the job packs become Apache-2.0.

## Decision

- **Licensing is off, compiled in.** `LICENSING_ON = False` in `surfsense_local/backend/modules/license/licensing.py`; only `SURFSENSE_LOCAL_LICENSING=1`, which the tests set, turns it on. `/license/status` reports it as `licensing`, so the frontend needs no flag of its own. With it off:
  - every job runs, with no licence or with one that ended;
  - the API starts neither the licence renewal nor the pack delivery; `POST /license/refresh` and `POST /job-packs/download` answer `409 licensing_off` and send nothing;
  - no plugin licence verdict is asked, and the licence key is never sent;
  - Settings › Network no longer lists `api.surfsense.com`;
  - the app hides the License section, the sidebar's licence row, and every licence offer, lock, trial and pricing link.
  Importing a licence and importing a pack stay, so a relaunch can read the files people already hold.
- **The licensing code and its tests stay**, so paid features can come back by flipping the constant.
- **The two job packs ship in the app.** The security questionnaire and the contract redline move from the private `surfsense-jobs` repository into `surfsense_local/backend/modules/jobs/packs/bundled/`, under Apache-2.0, signed with the existing pack key. The frozen backend carries them as data, and the API installs them at start: an installed version that is the same or newer stays.
- **Web search has no default server.** It stays off, with a sentence saying so, until the user names a SearXNG server in Settings › Network. Reading a link the user gives still works, with no server.
- **BSL code becomes Apache-2.0.** `backend/plugins/proprietary/` is Apache-2.0 like the rest of the repository, and anyone may change it.

## Consequences

- A paid customer's licence keeps nothing and loses nothing: every job runs for everyone.
- A user who never names a SearXNG server never searches; the agent's `surfsense_search_web` tells the model so.
- The hosted docs ([backend](../architecture/backend.md), [licence portal](../architecture/license/portal.md), [plugin host](../architecture/plugin-host.md) and the rest) describe code that is not running, kept for a relaunch.
- Relaunching licensing means a server again, the constant flipped, and the frontend's hidden surfaces showing once `licensing` is true.
