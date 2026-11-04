# ADR 0080: SurfSense sells one paid license, Business, priced per person

- **Status:** Accepted
- **Date:** 2026-11-01
- **Amends:** [ADR 0067](0067-b2b-jobs-ship-as-paid-plugins.md): who unlocks a job plugin, now a Business license or the 14-day trial, where its Decision says "Individual, Team, or the 14-day trial", and when a lapse stops it, now 30 days after a Business license lapses; [ADR 0019](0019-offline-licenses.md): which licenses are sold, Business alone from the release that ships the first paid job, and the same 30 days before a lapse stops new job runs. ADR 0019's offline verification, and its rule that a license never disables the app, stand.
- **Source:** [08 L742–745](https://github.com/MODSetter/SurfSense/blob/adbe2ce813043968f6868fcb024c576e4b5af208/plans/community-local/seo/08-b2b-artifact-jobs.md#L742-L745), maintainer decision, 1 Nov 2026 (no permalink)

## Context

ADR 0067 made SurfSense's B2B jobs paid plugins and left their price open: the Individual license ($60 the first year, then $120), or a business license at a higher price ([08, open question 2](../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer)). Individual sells the platform scrapers and priority support, and the scrapers retire ([ADR 0081](0081-surfsenses-scrapers-retire-and-web-pages-and-search-stay-free.md)).

The jobs' buyers are firms. AI tools for lawyers, accountants and clinicians run about $40–150 a month per user, and committed questionnaire-tool plans start around $3,000 a year; both figures are hypotheses.

A check in the open-source app can be stripped by a fork (ADR 0019), and a licensee can read a job's content, since the agent reads it as plain text and prompts reach the model. What holds is delivery only to a valid license, the license terms, and the firm's name on screen. No license is bound to a machine.

## Decision

- **One paid license, Business.** Business starts at one person, and a one-person Business license is shown as "Solo". Anyone who uses a SurfSense job plugin for work needs Business.
- **One switch, in the release that ships the first paid job.** Business goes on sale, the platform scrapers retire ([ADR 0081](0081-surfsenses-scrapers-retire-and-web-pages-and-search-stay-free.md)) and Individual sales stop in that one release, so the paid offer is never empty. Until then the scrapers and the Individual license stay on sale.
- **Only Business or the 14-day trial unlocks SurfSense's B2B job plugins.** The jobs, in order: the security questionnaire and DDQ first; RFP and RFI responses; bank statements into a ledger, medical chronologies, and contract and lease registers; the contract redline against a playbook. Later come firm controls (a firm-wide policy lock, a local audit log with exports for a WISP and HIPAA reviews, a people roster) and team features (a shared library, approval by a second person, sealed client workspaces).
- **A founding price per person:** $200 a year for the first person and $120 a year for each further person (1 person $200, 2 $320, 5 $680, 10 $1,280, 15 $1,880), locked for early customers and a hypothesis to test. It replaces the earlier plan of $1,200 a year per firm, and Individual's $60, then $120.
- **Yearly renewal on the same key.** Business renews automatically every year, and a renewal extends the same Keygen license. The app fetches the renewed license file when online, and an offline machine imports the emailed file. The checkout states the yearly renewal before payment. Cancellation and seat changes go through Stripe's customer-portal link, sent by email, so SurfSense still has no accounts ([ADR 0024](0024-portal-without-accounts.md)).
- **One trial:** 14 days of the full job, and no separate pilots; a design partner's trial is extended by hand. Two rules users are not shown: Gmail dots fold into one address, and a company domain gets at most two trials a year.
- **People, not devices.** The firm declares at checkout how many people use job plugins, and confirms the number at renewal. There is no device binding and no device identifier at launch. Device activation (two computers per person, a random per-install code, never a hardware ID, with consent and an offline path) is added only if download counts show sharing. Job screens show the firm's name.
- **Individual licenses already sold** keep what they bought until the switch, and their holders get a short notice that the scrapers retire. At the switch, each becomes Business Solo on the same key and keeps renewing at the price it was bought at, locked, as an early customer, with a notice email when converted and a reminder before each renewal.
- **A lapsed Business license stops new job runs 30 days after it lapses,** where ADR 0067 stops the job plugin when the license lapses. Every file, library and output stays readable.
- **What does not change.** The app stays free and Apache-2.0, everything it does today included, with the engines and the shared job machinery. ADR 0067's line stands: an edit is free, a job is paid. A license never disables the app.

## Consequences

- **Before Business is sold, five things must exist:** a Keygen policy for Business, with entitlements for the jobs; the license server issuing Business and handling yearly renewals and refunds; the app fetching a renewed file, a new outbound call that falls under egress consent ([ADR 0017](0017-egress-off-by-default.md)) and that the privacy page has to describe; ADR 0067's route for paid bundles and the job-pack loader; and the Business terms and the Job Plugin License, drafted with a lawyer.
- **New plans get new policies.** The live trial, individual and team policies are never edited or made strict: the plugin host accepts only `VALID`, so a strict policy would lock out every key on it. Keygen CE 1.7.2, which production runs, has all Business needs.
- **Billing.** The webhook ignores `invoice.paid`, so an automatic renewal would charge without extending the license, and a refund of a subscription charge cannot be traced to a license. Both are fixed before Business is sold, and the existing Individual subscriptions need the same fix before their first renewal. [Contract 1](../contracts/01-license-file.md) gains a `business` plan. The license server moves from the admin token to a product token, and validates a license before it creates a machine or checks out a file, since Keygen does not check license status there for admin or product callers.
- **Public promises change before Business is sold:** the purchase email's "The app never contacts a license server" and "works on every machine you install SurfSense on" ([`message.py`](../../backend/license/email/message.py) L58–59), and the same said of every computer on `/pricing/individual` and `/license/activate`; the pricing FAQ's "A paid licence is only needed for the scraper plugins and priority support" and "a single payment, not a subscription"; and Terms section 5, where a license adds the scraper plugins and "gates nothing else". The privacy page's "does not compute or transmit a device fingerprint" stays true at launch, since there is no device identifier.
- **Individual licenses sold before the switch** keep what they bought under Terms section 5 ("a licence you have already bought keeps the terms and price you bought it on"), the scrapers included, for their whole year, unless the Individual page and purchase email say from now that the license becomes Business Solo at the switch (open question q).

## Where the code stands

- No Business license exists. The portal sells Individual through a Stripe Payment Link and issues team licenses by hand; contract 1's `plan` is `trial`, `individual` or `team` ([portal](../architecture/license/portal.md#plan-resolution)).
- [`stripe_webhook.py`](../../backend/license/stripe_webhook.py) fulfils a paid checkout, suspends a license on a full refund, and drops every other event.
- The app never fetches a license file: a renewal is a new file the user adds ([license in the app](../architecture/license/app.md#settings-and-the-sidebar)).
- No job plugin exists, and neither the route for paid bundles nor the job-pack loader is built (ADR 0067), so Business has nothing to unlock until the questionnaire's beta, which 08 plans for about mid-January or mid-February 2027.

## Open

The full list is [08's open questions](../../plans/community-local/seo/08-b2b-artifact-jobs.md#open-questions-for-the-maintainer), lettered a to r. Those that bear on the license, with their recommended defaults:

- **a.** Is every job included in Business, or is each an add-on? Default: all included.
- **b.** Who counts as a person? Default: anyone who runs a job plugin, or has the agent use one, for the organization, employees and contractors alike, counted at the busiest month.
- **c.** How do shared servers, offline and air-gapped firms, shared PCs and virtual desktops count? [Docker](../architecture/docker.md#data-and-license) says today that one license works on a desktop and a server. Default: count people; a shared server needs a license for two or more people; offline firms pay the same price.
- **e.** Is job content kept in a private repository and shipped as signed packs under a closed Job Plugin License, with old pack versions published as open source after 12–24 months? Default: yes; the Business Source License, FCL, ELv2 and PolyForm Noncommercial all allow redistribution.
- **f.** If SurfSense stops selling Business licenses, do firms keep running the packs they have, on a pre-signed license held outside the company? Default: yes, on shutdown only; Enterprise may negotiate keeping old versions after any lapse.
- **g.** Which lawyer, budget and governing law, US first? Default: the Business terms, with audit and true-up clauses, and the Job Plugin License first.
- **j.** Is anything sold before the questionnaire passes 08's quality bar? Default: no; trials with design partners in December, and the paid launch with the mid-January beta.
- **k.** Self-serve up to how many people before a quoted Enterprise deal? Default: 15.
- **l.** What do any hand-issued Team licenses become? Default: they keep working to expiry and are offered Business at renewal.
- **m.** Is $200 the first person's price, as written, or a base fee before $120 per person? Default: the first person's price.
- **n.** Does Business include the priority support and the yearly feature build request that Individual carries? Default: yes.
- **o.** Where does the app fetch a renewed license file from? Default: SurfSense's license server, so the app still never contacts Keygen (ADR 0019).
- **p.** What does Enterprise keep once firm controls move into Business? Default: more than 15 people, a site license, an internal mirror, virtual desktops, a DPA, the code audit, named support, invoicing and negotiated terms.
- **q.** Do Individual licenses sold before the switch also become Business Solo at their price? Default: yes, said on the Individual page and in the purchase email from now.
