# ADR 0081: SurfSense's platform scrapers retire, and reading web pages, YouTube and search move into the app for free

- **Status:** Accepted
- **Date:** 2026-11-01, revised 2026-11-02
- **Supersedes:** [ADR 0025](0025-scraper-client-as-paid-plugin.md): the hosted scraper client shipping as a paid plugin. Its rules that a trial unlocks paid plugins ([ADR 0019](0019-offline-licenses.md)) and that a plugin's hosts need the user's consent ([ADR 0017](0017-egress-off-by-default.md)) stand.
- **Amends:** [ADR 0047](0047-premium-plugins-are-source-available.md): its first paid plugins being remote ones on SurfSense's servers, the scrapers; [ADR 0054](0054-surfsenses-plugins-run-on-one-plugin-host.md): the plugin host running SurfSense's plugins "free and paid", with one scraper plugin per platform; [ADR 0068](0068-surfsense-calls-its-own-plugins-to-pull-a-link-into-sources.md): "The license is the gate" for Add from the web, its pullers for the retired platforms, and where the remaining pullers run
- **Source:** maintainer decisions, 1 and 2 Nov 2026 (no permalink)

## Context

The plugin host runs ten scraper plugins, each needing a SurfSense license ([plugin host](../architecture/plugin-host.md)): Google Search, Web Crawl, Reddit, YouTube, Instagram, TikTok, Google Maps, Amazon, Walmart and Indeed. The pricing page already leaves out Reddit and Instagram, which close their public pages to readers who are not signed in. PostHog shows that people use three of them to add sources from the web: Web Crawl, YouTube, and Google Search, whose SearXNG fallback answers when Google walls the host. The others go almost unused. They cost upkeep, residential proxies and captcha solving: Google walls most residential IPs, and a paid solver passes its reCAPTCHA page.

SurfSense's paid offer moves to the B2B job plugins, which run on the user's machine ([ADR 0067](0067-b2b-jobs-ship-as-paid-plugins.md)) and unlock with a Business license ([ADR 0080](0080-surfsense-sells-one-business-license-priced-per-person.md)). Add from the web ([ADR 0068](0068-surfsense-calls-its-own-plugins-to-pull-a-link-into-sources.md)) routes a link to its site's own puller, and any other link to Web Crawl ([`links.py`](../../surfsense_local/backend/modules/documents/web_sources/links.py)), and it searches through the Google Search plugin.

## Decision

- **Seven platform scrapers retire:** Google Maps, Amazon, Walmart, TikTok, Indeed, Reddit and Instagram.
- **Reading web pages, YouTube and web search move into the app, free and under Apache-2.0.** They run on the user's machine, with no license; pages and transcripts come straight from their sites, and searches go to a SearXNG server, SurfSense's hosted one by default:
  - page reading with `trafilatura` and `curl_cffi`, without stealth browsers;
  - YouTube transcripts, fetched over the user's own connection;
  - web search through SearXNG, by default SurfSense's hosted instance, with a setting for the firm's own.
- **The Google scraper is dropped.** SearXNG can include Google among its engines, and the scraper needed residential proxies and a captcha solver.
- **All of it happens in the release that ships the first paid job,** the same release in which Business goes on sale and Individual sales stop ([ADR 0080](0080-surfsense-sells-one-business-license-priced-per-person.md)), so the paid offer is never empty. Until then the scrapers stay on sale.
- **No paid plugin is left on the plugin host.** SurfSense's paid plugins are now the job plugins, which run on the user's machine (ADR 0067).

## Consequences

- **Add from the web keeps working, with or without a license.** A link to a retired platform falls back to page reading. Searching inside one retired site, such as Amazon, goes away with that site's puller, and the remaining searches go through SearXNG.
- **The app changes in that release.** Its first-party list keeps only the three, now built in; `links.py` drops the seven pullers; Add from the web stops refusing a request with no license, and its license offer goes.
- **Each site the app reaches follows egress consent** ([ADR 0017](0017-egress-off-by-default.md), [ADR 0027](0027-egress-consent-per-host.md), [ADR 0060](0060-one-consent-question-per-user-action.md)). Pages and searches now go from the user's machine to the sites and to SearXNG, and the privacy page says so.
- **The hosted plugins keep running for older apps,** which call them with a license, until the maintainer switches the host off. DataImpulse and capsolver can then be cancelled. SurfSense's hosted SearXNG stays, with a limit per IP address.
- **Individual license holders get a notice** under Terms section 18, which promises an email to the license's address for a material change; section 5 still governs any refund. Because the scrapers retire only when the first job plugin ships, a license or a trial always unlocks something.
- **Until the switch the scrapers keep running.** Keeping them as they are, with no new fixes, is recommended ([08's open question r](../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)).
- **Wording that sells the scrapers changes in that release:** the trial, offered as "a 14-day licence for the scraper plugins"; the pricing card and FAQ that list the platforms; Terms sections 5 and 6, on the scraper plugins and the service behind them; `/plugins`; and the README's plugin table, in every locale, which loses seven rows and marks the three as free.
- **Code moves into the Apache tree.** The page reading, YouTube and search code is copied from `backend/plugins/proprietary/`, which is under the Business Source License, into `surfsense_local/` under Apache-2.0, which SurfSense's copyright allows. Maintainers retire the rest of that folder, which only they change (ADR 0054).
- **The installer stays within its size budget.** The new Python dependencies are small, and stealth browsers are left out.

## Where the code stands

- The scrapers still run on the plugin host: ten plugins in [`backend/plugins/proprietary/`](../../backend/plugins/proprietary/), each refusing a request without a valid license ([plugin host](../architecture/plugin-host.md#the-license-check)).
- The app still lists all ten first-party plugins, each with `access: license` ([`plugins.json`](../../surfsense_local/backend/modules/plugins/lists/first_party/plugins.json)), and `links.py` still sends eight platforms' links to their own pullers.
- Add from the web refuses a request with no license, `403 license_refused` ([web sources](../architecture/web-sources.md#routes)). Its web search calls the Google Search plugin, which renders Google through the proxy and the solver and falls back to SearXNG only when Google walls every IP and `SEARXNG_URL` is set.
- The move into the app is being built for the release that ships the first paid job.
