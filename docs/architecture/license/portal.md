# License portal

The one [backend](../backend.md) sells, delivers and re-delivers the desktop app's license file, and serves a license the job packs its jobs unlock, with no accounts and no license table. Stripe and Keygen are the system of record: every search is a filter over Keygen license metadata, and the one direct read is by a derived id, and the license routes take no session, read no user table and touch no Postgres. Control of an inbox replaces the login, because a license is only ever mailed to the address it is registered to. Where having no table would cost a guarantee, the code moves the guarantee into Keygen instead of adding a table. Stripe and Keygen hold everything but the job packs, which are a private repository's GitHub releases that the server reads, checks and keeps in memory ([job packs](#job-packs)).

**Code:** [`backend/license/`](../../../backend/license/), [`backend/mailer/`](../../../backend/mailer/), [`www/app/(home)/license/`](../../../www/app/\(home\)/license/)
**Decisions:** [ADR 0024](../../adr/0024-portal-without-accounts.md), [ADR 0019](../../adr/0019-offline-licenses.md), ADR 0079 (one Business license, priced per person; on the `docs/business-license` branch), [ADR 0081](../../adr/0081-the-license-server-delivers-job-packs-from-private-releases.md)

What the routes produce is [contract 1](../../contracts/01-license-file.md), which the [desktop app](app.md) consumes, and for job packs [contract 6](../../contracts/06-job-pack-delivery.md), which no app on dev reads yet.

## Routes

All under `/api/v1`, unauthenticated, FastAPI routers that [`portal.py`](../../../backend/license/portal.py) groups and the [backend's](../backend.md) app includes only when `KEYGEN_API_TOKEN` is set. The backend's CORS lets in `NEXT_FRONTEND_URL`, its www or bare twin and localhost, exposing `Content-Disposition`:

| Route | Answers |
|---|---|
| `GET /license/file?session_id=` | the `.lic` for that checkout session, or 404 |
| `POST /license/resend` `{email}` | 200 with the same body whatever it found |
| `POST /license/trial` `{email, channel?}` | 200 once the trial is mailed |
| `POST /license/refresh` `{key}` | the license's current `.lic`, for the app after a renewal |
| `POST /license/job-pack` `{key, entitlement, installed_version?, runners}` | the newest job pack the license may run, as a zip; 204 when the app's is current |
| `POST /stripe/webhook` | purchases, renewals, seat changes, ended subscriptions, refunds and disputes |

Resend and trial validate `email` as an email address and answer 422 for anything else. A request that breaks a route's rules gets a 422 whose `detail` lists each error's `type`, `loc` and `msg` and never its input (`server/app.py`), since these bodies carry an email address or a license key. The trial's optional `channel` is the site's acquisition tag ([funnel events](#funnel-events)); it is kept only when it matches `^[a-z0-9_-]{1,40}$` and is dropped otherwise, never refused, so a bad tag cannot cost anyone a trial.

### `GET /license/file`

The success page's download. It lists Keygen licenses whose `metadata[checkoutSessionId]` is `session_id` and checks out a fresh file, unless the license no longer validates ([check-out](#keygen-as-the-database)), as after a refund, which reads as a miss. On a miss, when Stripe is configured, it retrieves the session and runs the same fulfilment as the webhook, because the buyer lands on the success page seconds after paying and `checkout.session.completed` can arrive later. A session that is missing or is not a license purchase is 404, and a Keygen failure is 500. `session_id` is required, since there is no signed-in user to fall back to. The answer is `text/plain` with `Content-Disposition: attachment; filename="surfsense.lic"`. The route needs no mail, which is why the success page, not the email, is the reliable delivery path.

### `POST /license/resend`

1. `503` when `SMTP_ENABLED` is false or the SMTP configuration is invalid, before anything else.
2. The rate limits below; `429` when either bucket is empty.
3. List licenses by `metadata[email]`, skip `SUSPENDED` and `BANNED` ones, check out a fresh file for each that still validates and mail them all in one message, in the Business copy when any of them is a Business license or trial.
4. `200` with "If a license is registered to that address, it is on its way.", whether it found three licenses or none, and also when the recipient's server refused the address.

After the success page this is the only way to get a license back, so an answer that varied with the outcome would make it an oracle for who is a customer. Skipping suspended licenses keeps it consistent with refunds. A transient mail failure or a Keygen failure answers 503.

### `POST /license/trial`

1. `404` when `LICENSE_TRIAL_ENABLED` is off; `503` when mail is off or misconfigured.
2. The rate limits, then `400` for a disposable domain, looked up as [Email addresses](#email-addresses) describes.
3. `409` when a license on the trial policy already carries this address's folded form in `metadata[trialKey]`.
4. Create the trial under a derived id with an explicit expiry, check it out and mail it: `200`. `license_trial_issued` is emitted once the trial exists, before the mail, since the address is spent either way.

The file is never in the response. Delivery to a real inbox is what makes one trial per email mean anything; handing the file back over HTTP would make unlimited trials a loop over throwaway strings. Unlike resend, trial has to say "already claimed", so it reports each outcome, including the ones after the create: a Keygen failure answers 503 and points at resend, which finds a trial that was created but not mailed; a transient mail failure answers 503 saying the trial exists; a refused recipient answers 400.

The expiry is `max(now, LICENSE_TRIAL_EXPIRY_FLOOR) + LICENSE_TRIAL_DAYS`, 14 days by default. The floor is for trials issued before the first plugin ships, so the wait does not eat the trial. Unset, the rule is plain "days from now"; an unparseable floor is ignored with a warning.

`LICENSE_TRIAL_BUSINESS`, off by default, switches the route to Business's trial on launch day. The trial is then a `trial` on the `KEYGEN_POLICY_BUSINESS_TRIAL` policy, with `jobs` in its metadata, mailed in the Business copy. Its derived id is `business-trial:<folded email>` and its `trialKey` check filters on that policy, so a person who took the earlier trial, which unlocked only the scrapers, can still try the job once. The plan stays `trial`, so the app and the [cohort report](#cohort-report) count it as one. With the switch on and the policy unset, the route answers 503 before any Keygen call, since a trial on the old policy would spend the address on a trial without the job.

### `POST /license/refresh`

The app's way to pick up a renewal: a renewal extends the same key, so the app sends the key it holds and gets a fresh file carrying the new expiry ([contract 1](../../contracts/01-license-file.md), producer rule 7). The key goes in the JSON body, never the URL, which ends up in logs.

1. The [rate limits](#rate-limits): one bucket on the caller's IP and one on the key, named by a hash so the key never sits in Redis; `429` when either is empty.
2. `validate-key` on Keygen, unscoped, as the product token, which reads a key of another product as unknown.
3. `404` "No license has that key." for `NOT_FOUND`; `403` naming the code for any other code than `VALID` or `EXPIRED`, as for a suspended license; otherwise a fresh file, `text/plain` with `Content-Disposition: attachment; filename="surfsense.lic"` and `Cache-Control: no-store`.
4. `503` when Keygen fails.

A lapsed license still gets its file, which says what the app already shows. Naming the state leaks nothing, since the key is the credential the file already carries. The app does not call the route yet; [the app](app.md#settings-and-the-sidebar) still takes a renewal as a new file the user adds.

### `POST /license/job-pack`

The app's way to get the jobs a license includes: it sends the key it holds, one job code from the license's `jobs`, the version it has of a pack with that job, and the job runners it ships, and gets the newest pack that license and that app may run, as the pack's signed zip, from this host ([contract 6](../../contracts/06-job-pack-delivery.md), [job packs](#job-packs)). As for the refresh, the key goes in the JSON body. `job_packs/route.py` answers at the first check that fails, in this order:

1. The body's rules (`job_packs/schemas.py`): `key` 1 to 1,024 characters once trimmed, as the refresh takes it; `entitlement` matching `^[A-Z][A-Z0-9_]{0,63}$`; `installed_version` `x.y.z` or absent; 1 to 16 `runners` matching `RUNNER_PATTERN`, such as `workbook-rows/1`. A field the route does not know is ignored. Anything else is a `422` that lists each error's `type`, `loc` and `msg` and echoes nothing, the key included: it is always the caller's bug.
2. The [rate limits](#rate-limits), the address's bucket first: `429` `rate_limited`.
3. `422` `unknown_job` when `entitlement` is not in `jobs.py`, before any Keygen call.
4. `validate-key` on Keygen, unscoped, as the product token (`job_packs/verdict.py`): `404` `license_not_found` for `NOT_FOUND`, and `403` `license_not_valid`, naming Keygen's code, for any code but `VALID`. A Keygen failure is `503` `job_packs_unavailable`, logged without the key.
5. `403` `job_not_included` when the license's `jobs` does not list `entitlement`.
6. The packs in the [store](#the-store): `503` `job_packs_unavailable` when no store is set, when the store has not answered since the backend started, or when no pack with a job for `entitlement` is published, each logged at ERROR.
7. Coverage (`job_packs/selection.py`): of the packs with a job for `entitlement`, those whose every job's entitlement the license's `jobs` lists; none is `403` `pack_not_covered`.
8. Runners: of those, the packs whose every job's runner is in `runners`; none is `409` `needs_newer_app`. The highest `version` left is the pack.

Then `204` when `installed_version` is that version or newer, or else `200` with the zip as `application/zip` and `Content-Disposition: attachment; filename="<id>-<version>.zip"`. Both carry `X-Job-Pack-Id`, `X-Job-Pack-Version`, which on a `204` is the newest version this license and app may get, and `Cache-Control: no-store`. Every refusal is `{"detail": {"code": "<code>", "message": "<a sentence>"}}`. The `503`s share one code: a Keygen failure says "Could not check that license right now. Try again later.", and the store's cases in item 6 all say "Jobs cannot be downloaded right now. Try again later.", told apart only by the server's ERROR log.

Unlike the refresh, `EXPIRED` gets nothing. A Business license's expiry already falls 30 days after the year paid for, and a trial ends at its expiry, so a lapsed license keeps the pack it has and gets no newer one, though the refresh still serves it its file. `jobs` is read as the app reads it, and Keygen's policy entitlements are not read, so the server never sends a pack the app would keep locked. Coverage is why every job of a paid pack carries an entitlement: the app installs every job of a pack it accepts, so a pack holding a job the license lacks is withheld whole. It has its own code, `pack_not_covered`, since the license does list the job asked for and the app must not say it does not. The runner filter is why an older app is never sent a pack it would refuse: a pack that needs a new runner or a later schema names a runner only the apps that have it list.

The server keeps nothing about a request beyond the rate limits' counts, dropped an hour after the caller's last request, and its access log line; Keygen notes when the license was last validated. The route's own logs carry no key, address or body, and no analytics event is sent for a delivery. No app on dev calls it yet: the app's side is on the `feat/jobs-in-app` branch.

### Stripe webhook

`stripe_webhook.py` verifies the signature and acts on the seven events below; any other event, a credit purchase of the hosted product included, is acknowledged and dropped. Stripe's calls run in a worker thread, since the event loop also streams every plugin call. A purchase, renewal or seat change that fails answers 500, so Stripe retries: a fulfilment is safe to repeat by its derived id, and a renewal or seat change sets the same values again.

- `checkout.session.completed` with `payment_status` `paid` or `no_payment_required`, and `checkout.session.async_payment_succeeded`: the license handler claims a session whose metadata says `purchase_type: license`, or, with no `purchase_type` and a license price configured, whose line item is a license price. It fulfils the session, then emails the file, in the Business copy for a Business license. A mail failure does not fail the webhook: the license exists, the success page serves it, and a Stripe retry would only risk a duplicate. A subscription's checkout also writes `stripeSubscriptionId` and ends the license with its first period ([subscriptions](#subscriptions)). A Business checkout writes `jobs`, its quantity as `maxUsers`, and `firm` from the checkout's custom text field keyed `firm`, with its spaces collapsed and cut to 120 characters; a checkout without that field still issues the license.
- `invoice.paid`: a paid period renews the same license ([subscriptions](#subscriptions)).
- `customer.subscription.updated`: a Business license's `maxUsers` follows the subscription's quantity, and nothing else moves, since Stripe advances the period in this event before the renewal is paid.
- `customer.subscription.deleted`: nothing changes in Keygen, and the log says when the license lapses. Its expiry already ends the last period paid for plus 30 days, and with no paid invoice nothing extends it; suspension is for money returned.
- `charge.refunded`: acts only on a full refund, `refunded` or `amount_refunded >= amount`; a partial refund suspends nothing. It traces the charge's `payment_intent` to the one license it paid for and suspends that license alone, so a customer's other purchases keep working. A subscription's charge belongs to an invoice, not to a checkout session, so the trace asks Stripe's invoice payments for the invoice, reads its subscription (under `parent.subscription_details` since API 2025-03-31) and finds the license as [subscriptions](#subscriptions) does. A payment with no subscription invoice is a one-time one, traced to its checkout session and that session's license by `checkoutSessionId`. The charge's customer is not needed: a Payment Link's default `customer_creation` makes none for a one-time price, and such refunds used to be skipped. A charge for an invoice that pays for no period, the `subscription_update` proration for people added mid-year, traces to no license, since the year is still paid for. A refund that traces to no single license suspends nothing and logs a warning for support, because a wrong suspension is silent to the customer. Failures are logged and the webhook still answers 200, since a retry would re-run the suspension. Suspend, not revoke: it is reversible, the record stays listable for support, and Keygen's `validate-key` then reports `SUSPENDED`, which contract 2 maps to `revoked`. Refunding does not cancel the subscription; support cancels it in Stripe too, or a suspended license goes on being charged.
- `charge.dispute.created`: suspends the license the disputed payment paid for, traced the same way. A dispute won later is reinstated by support.

Fulfilment also writes the license's Keygen id onto the Stripe customer as `keygen_license_id`, best effort, so a Stripe error cannot fail the webhook. Nothing reads it back; refunds find licenses through Keygen metadata.

### Funnel events

The licence server counts two funnel steps in PostHog through an opt-in client (`analytics.py`; nothing is sent without `POSTHOG_API_KEY`), stamped `source: backend` as before the move. `funnel/events.py` sends both personless: a fresh random distinct id per event and `$process_person_profile` false, with GeoIP off. The properties are the whole payload; no email, licence id or key, Stripe customer or session ever goes with them.

| Event | Emitted | Properties |
|---|---|---|
| `license_trial_issued` | by the trial route once Keygen holds the new trial | `channel` |
| `license_purchased` | by `fulfill_license_session()` when it mints the licence | `plan`, `amount_total` (Stripe minor units), `currency`, `channel` |

The purchase event comes from fulfilment rather than the webhook because the webhook and the success page both fulfil a payment; only the caller whose create succeeded emits it, so each purchase counts once. Its `channel` is the session's `client_reference_id`, which the site's Payment Link carries ([pages](#pages)); anyone can edit that link, so it is reduced to the tag alphabet (lowercased, other characters folded to `-`, 40 characters) rather than trusted. A request with no usable channel is counted as `unknown`, apart from the site's own `direct`.

### Plan resolution

`resolve_license_plan()` reads the plan two ways, so a Payment Link and an API-created session both work. Session metadata with `purchase_type: license` comes first (`plan` of `individual`, `team` or `business`, and `quantity` for team and business); otherwise the line item's price ID is matched against `STRIPE_PRICE_LICENSE_INDIVIDUAL`, `STRIPE_PRICE_LICENSE_TEAM` and `STRIPE_PRICE_LICENSE_BUSINESS`, with the line item quantity as the team's seats or the Business license's people, in `maxUsers`. Business is one graduated yearly price, $200 for the first person and $120 for each further one, so its quantity is the number of people. Webhook payloads carry no line items, so a Payment Link purchase costs one extra Stripe call. The site sells Individual through a Payment Link and no longer sells Team; the backend still supports it, and `scripts/issue_enterprise_license.py` issues team licenses by hand.

### Subscriptions

Business renews every year on the same key (ADR 0079), and the Individual Payment Link has sold yearly subscriptions too, so a license sold on a subscription follows it. `subscription/` holds the rules:

- **Expiry.** The license ends 30 days after the period paid for: the grace before a lapsed Business license stops new job runs, which also covers Stripe's retries of a failed renewal. The period's end is read from the subscription's items, where API 2025-03-31 moved it, or from the subscription in an older payload.
- **Renewal.** On `invoice.paid` the subscription is read live, and the license's `expiry` moves to its period's end plus 30 days, only ever later. A Business license's `maxUsers` takes the subscription's quantity too, since the firm confirms its people at renewal. Reading the live subscription makes a retried or late event set the same values. A renewal (`billing_reason` `subscription_cycle`) that moved the expiry mails the renewed file, so a computer that stays offline can import it; a suspended license is extended but gets no file. The first invoice (`subscription_create`) usually comes before the checkout's event and finds no license, which the checkout then mints with that period's expiry.
- **Finding the license.** By `metadata[stripeSubscriptionId]`. A license sold before that key was written, such as an existing Individual subscription, is found through the checkout session that started the subscription and gets the key on its next renewal, so each renews on its own key. Its price is Stripe's alone; nothing here touches a subscription. Two licenses on one subscription are a support case, never a guess.
- **Only the attributes that change.** A renewal or a seat change sends `expiry` and `maxUsers` alone, so it never rewrites metadata support corrected; only writing `stripeSubscriptionId` on an older license sends the metadata, whole, from the record just read.

## Keygen as the database

| Metadata key | Set on | Used by |
|---|---|---|
| `plan` | every license | the app (contract 1) |
| `email` | every license | delivery, resend, shown in Settings |
| `trialKey` | trials | the one-trial-per-person check |
| `stripeCustomerId` | Stripe purchases | the Stripe customer the purchase came from |
| `checkoutSessionId` | Stripe purchases | the success page, support corrections, a one-time payment's refund → suspend |
| `stripeSubscriptionId` | subscription purchases | renewal, seat changes, a subscription charge's refund or dispute → suspend |
| `firm` | Business, when the checkout's field was filled | the app's job screens (contract 1) |
| `jobs` | Business and its trial | the app (contract 1): which job plugins the license unlocks; the [job pack route](#post-licensejob-pack): which packs the license may get |

Keygen snake-cases metadata keys when it stores them and when it filters on them, and camelCases them in responses ([`jsonapi.rb`](https://github.com/keygen-sh/keygen-api/blob/v1.7.2/config/initializers/jsonapi.rb#L5-L11), [`license.rb`](https://github.com/keygen-sh/keygen-api/blob/v1.7.2/app/models/license.rb#L337-L338)), so `checkoutSessionId` and `checkout_session_id` are one key. A key with a different word is what goes wrong: it returns an empty list rather than an error, which reads as "no license". The spellings live in `app/license/models.py`, except that `create_license()` in `keygen.py` writes `plan` and `email` as literals.

Certificates are never stored. Every delivery, whether success page, purchase or renewal mail, resend or the app's refresh, checks out a fresh file with `{"meta": {"ttl": null}}`, so two files for one license differ in `meta.issued` and share a key. `ttl: null` matters because the app keeps a file until it imports a newer one, and Keygen's default 30-day TTL would kill every file a month after purchase.

Every check-out follows an unscoped validation (`fresh_file.py`): `POST /licenses/{id}/actions/validate`, or `validate-key` for the refresh, and a file only when Keygen answers `VALID` or `EXPIRED`. Keygen checks no license status when a product or admin token checks a file out, so without it a refunded, suspended license would still get a fresh file from the success page. `EXPIRED` passes because the file carries the expiry the app already shows, and a lapsed trial's resend has always been answered. Unscoped, because the server names no machine or fingerprint and no policy of ours requires a scope. The server creates no machines.

The [job pack route](#post-licensejob-pack) validates the same way, `validate-key` unscoped as the product token (`job_packs/verdict.py`), but passes `VALID` alone and checks nothing out. A file only restates the expiry the app already shows, so `EXPIRED` may have one; a pack is a newer job to run, which a lapsed license does not get.

Each plan has its own policy, and `jobs.py` lists the job entitlement codes, `JOB_QUESTIONNAIRE` first: the setup script attaches each to both Business policies, where Keygen holds them, and every Business license and trial copies them into `jobs`. `jobs` is the one list both sides read. The app unlocks a job from it offline, and the job pack route reads it from `validate-key`'s answer as the app reads it (`jobs_of()`): split on commas, each code trimmed, empty and repeated codes dropped, and nothing at all from a value that is not a string. The policies' entitlements, which every license on a policy inherits and which can disagree with `jobs`, are never read, so the server never delivers a pack the app would keep locked.

| Policy | Setting | Made by |
|---|---|---|
| trial, individual, team | `KEYGEN_POLICY_TRIAL`, `_INDIVIDUAL`, `_TEAM` | by hand, live; never edited or made strict |
| business | `KEYGEN_POLICY_BUSINESS` | the setup script: 395 days, the fallback for a license made without an expiry |
| business-trial | `KEYGEN_POLICY_BUSINESS_TRIAL` | the setup script: 14 days |

The live trial, individual and team policies are never edited or made strict: the plugin host accepts only `VALID`, and a strict policy answers `NO_MACHINE` for every key on it, which would lock all of them out. The setup script makes both Business policies non-strict and floating with no machine cap, since Business counts people, not devices (ADR 0079), with the live policies' signing scheme, so their files carry the `alg` the app accepts.

## Idempotency without a table

The Keygen license id is derived, not assigned: `uuid5` of a fixed namespace and `stripe:<checkout session id>` for a purchase, `trial:<folded email>` for a trial, or `business-trial:<folded email>` for the Business trial. When the webhook and the success page fulfil one payment at the same moment, both create the same id and Keygen refuses the second, with `422 ID_CONFLICT` when the first is already committed or a bare `409` when both are in flight, which the client confirms by fetching the id. For a purchase the loser reads the winner's license and delivers that; for a trial it answers 409. There is no lock and no table, and a second fulfilment cannot mint a second license; this replaces the earlier design of a Keygen lookup under a short Redis lock.

Only the id is derived. The license key stays Keygen-generated, because it is the bearer credential contract 2 sends to the scraper API and must be unguessable. The namespace is a constant rather than configuration, because changing it changes every derived id.

A trial has two guards. The derived id is the constraint that settles simultaneous claims; `trialKey` is a mutable index, so correcting an address can move it, which an id fixed at creation cannot follow.

## Email addresses

Delivery uses the address as typed, trimmed and lowercased. Deduplication, meaning the trial check and the per-email rate limit, also strips a `+tag` from the local part. `user+surfsense@gmail.com` is a real address the buyer may want the file at, so delivery must not fold it, but plus-tagging is the cheapest trial farm, so the trial check must. Dots are not folded: that is Gmail's rule, and applying it everywhere would collide distinct addresses at other providers. A trial stores both forms, `email` as typed and `trialKey` folded.

The trial's disposable check reads only the domain. The list is the community [disposable-email-domains](https://github.com/disposable-email-domains/disposable-email-domains) list, installed as the `disposable-email-domains` package, plus three domains our earlier hand-kept list refused and it does not carry; `LICENSE_DISPOSABLE_EMAIL_DOMAINS` adds more per deployment. The domain and every domain above it short of the TLD are looked up, because the list names registrable domains and a disposable service can mint any subdomain under one. The lookup uses punycode, the spelling the list is written in, since `EmailStr` hands the route Unicode even when punycode was typed. The package is pinned in `uv.lock`, so the list changes only with a reviewed bump, `uv lock --upgrade-package disposable-email-domains`; upstream publishes most days. A unit test fails such a bump if it would refuse a mainstream provider.

## Rate limits

Each POST draws on two buckets, the address's first, through a Redis token bucket on `REDIS_URL` (`token_bucket.py`), which falls back to per-process memory when Redis is down or unset rather than failing closed:

| Bucket | Default per hour |
|---|---|
| `license:<route>:ip:<ip>` | 10 (`LICENSE_RATE_LIMIT_IP_PER_HOUR`) |
| `license:<route>:email:<folded>` | 5 for resend, 3 for trial (`LICENSE_RESEND_RATE_LIMIT_PER_HOUR`, `LICENSE_TRIAL_RATE_LIMIT_PER_HOUR`) |
| `license:refresh:ip:<ip>` | 60 (`LICENSE_REFRESH_RATE_LIMIT_IP_PER_HOUR`) |
| `license:refresh:key:<sha256 of the key>` | 30 (`LICENSE_REFRESH_RATE_LIMIT_PER_HOUR`) |
| `license:job-pack:ip:<ip>` | 120 (`LICENSE_JOB_PACK_RATE_LIMIT_IP_PER_HOUR`) |
| `license:job-pack:key:<sha256 of the key>` | 60 (`LICENSE_JOB_PACK_RATE_LIMIT_PER_HOUR`) |

The refresh gets more room than resend and trial because a firm's people share one key and often one address. The job pack route gets twice the refresh's: the same people share its key and address, and each of their apps asks once per job at every start, every daily check and every user action that fetches jobs. Its `429` carries the code `rate_limited`, like its other refusals. A key's bucket is named by the first 32 hex digits of the key's sha256, so the key never sits in Redis.

The address's bucket is checked first, on every route, and the email's or the key's is spent only when the address is admitted, so a caller refused by its address spends nothing from the bucket of the email or key it names, which other callers may share. A memory bucket is forgotten an hour after its last use, when it would be full again anyway: each request drops the buckets idle that long, and while the portal is served its lifespan sweeps them every minute, so a caller's buckets go within a minute of that hour even when no request follows. Memory holds at most 100,000 of them, dropping the least recently refilled; Redis expires its buckets after the same hour.

The caller's address comes from `get_real_client_ip()` (`client_ip.py`), which reads only the header `LICENSE_CLIENT_IP_HEADER` names, `x-real-ip` by default, which Coolify's Traefik sets to the caller's address, taking the first entry when the header holds a list. With the setting empty, or the header missing or empty, it is the socket peer; a missing header is logged once per process as a warning that names the header, never an address, since behind the proxy every caller would then share one bucket. A header a caller can set, such as `CF-Connecting-IP` or `X-Forwarded-For`, is never trusted unless the setting names it, so a forged one cannot give a caller fresh buckets. The limits also bound mail spend and check-out load, since one resend is one check-out per license. A limit of zero turns its bucket off.

## Mail

[`backend/mailer/`](../../../backend/mailer/) is a port with one transport: `protocol.py` holds the `Mailer` protocol, the frozen `OutboundEmail` and `Attachment` payloads and the two errors; `factory.py` builds the mailer; `smtp.py` sends. The connection is deployment-wide (`SMTP_*`, read by `settings.py`), not license-specific, and each feature stamps its own sender on its messages. SMTP is the transport because every transactional provider speaks it, Resend, Postmark, SendGrid, Mailgun, SES and Brevo among them, so choosing a vendor is filling in host, port, username, password and a From address. The sender is stdlib (`email.message` and `smtplib` through `asyncio.to_thread`), one connection per send, and adds no dependency.

- `SMTP_ENABLED` defaults to false, and there is no pretend-to-send mode. Both POST routes check it first and answer 503, because a resend that always answers 200 over a mailer that silently drops mail would make a broken deployment look like a working one. The same check builds the mailer, so a bad `SMTP_*` setting also answers 503, before any Keygen call. Failing at startup instead would take every route down over a mail setting.
- `SMTP_SECURITY` is explicit, `starttls` by default, `tls` or `none`, never guessed from the port. `none` is refused when a username is set, so credentials never cross in the clear; without one it only logs a warning for a non-loopback host.
- Every send failure maps to one of two errors; a configuration error is neither: a bad setting raises `ValueError` when the mailer is built, which the routes turn into the 503 above. `MailerUnavailableError` covers connect failures, timeouts, 4xx replies, authentication failures and a refused sender, all ours to fix. `MailerRejectedError` is a permanent 5xx refusal during the conversation, of the recipient or of the message. A hard bounce arrives after a 250 accept, so trial promises "sent", never "delivered".
- `OutboundEmail.idempotency_key` is carried and ignored by SMTP, so a future API transport can dedupe retries without changing any caller.

`email/message.py` builds the four license messages, `purchase`, `resend`, `trial` and `renewal`, sent from `SMTP_LICENSE_FROM` or else `SMTP_FROM`, with `SMTP_LICENSE_REPLY_TO`. The file travels as `surfsense.lic`, numbered when one resend carries several, typed `application/octet-stream` so no mail client renders it inline and mangles its line endings. The install steps link each platform's installer through the site's download redirect, `https://www.surfsense.com/downloads/<platform>?src=email&v=<tag>`, with the tag pinned in `release.py`. The `v` keeps a mail already sent naming the build it was sent for, and the redirect counts the downloads mail produces ([updates](../updates.md#download-links)).

A Business license or trial gets its own copy of each, chosen by `BusinessCopy.of()` for a license on the business plan or one that lists `jobs`, and a resend takes it when any of its files is one. The Individual purchase mail promises that the file works on every machine and that the app sends the license key to the license server only when the user chooses Check for renewal; neither holds for Business, whose jobs the app downloads by itself, whose renewed file it fetches, and which counts people, so the Business copy says neither. It names the firm and how many people the license covers, says it renews every year on the same key until cancelled, and gives `STRIPE_CUSTOMER_PORTAL_URL`, the customer portal's login link, for adding or removing people and cancelling, or says to reply when that is unset; SurfSense still has no accounts. The Business trial says only new job runs stop when it expires. The renewal mail, sent for every plan, carries the renewed file and asks for it to be imported; the Individual copy of it is the only way that renewal reaches the app. The Business purchase and trial mails add a fifth step: when the app asks to reach the license server, allow it, so it downloads the job, then upload a questionnaire and policies to Sources and press Run beside Security questionnaire in Jobs. Resend and renewal mails, and every Individual mail, keep four steps.

## Keygen

Production runs a self-hosted Keygen CE. Keygen Cloud bills per active licensed user and counts a check-out as activity, and here every delivery, trials included, is a check-out. `keygen.py` talks to `KEYGEN_API_URL`, or to Keygen Cloud when that is unset; when `KEYGEN_HOST` is set it sends that name as `Host` and adds `X-Forwarded-Proto: https`. `KEYGEN_ACCOUNT_ID`, `KEYGEN_API_TOKEN` and the five `KEYGEN_POLICY_*` variables mean the same on either.

`KEYGEN_API_TOKEN` is a product token for the product every policy belongs to, and the admin token stays offline. A product token creates, reads, updates, validates, checks out and suspends its own product's licenses and creates its policies, which is all the server does; it cannot create entitlements or product tokens, so the setup script runs once with the admin token in `KEYGEN_API_TOKEN`. A product token lists only its own product's licenses, and a list that misses a license reads as "no license", so the setup script refuses when the live policies span products. CE is not a service in `docker/docker-compose.yml`; its web and worker images are in [`docker/keygen/`](../../../docker/keygen/).

Three things break a CE instance's first boot or first call:

1. Setup needs four secrets, `SECRET_KEY_BASE`, `ENCRYPTION_DETERMINISTIC_KEY`, `ENCRYPTION_PRIMARY_KEY` and `ENCRYPTION_KEY_DERIVATION_SALT`. Given those plus `KEYGEN_ACCOUNT_ID`, `KEYGEN_ADMIN_EMAIL`, `KEYGEN_ADMIN_PASSWORD`, `KEYGEN_EDITION=CE` and `KEYGEN_MODE=singleplayer`, `setup` runs non-interactively.
2. `KEYGEN_HOST` must be a dotted name with a parseable eTLD+1. A single label, `localhost` or a bare compose service name, crashes boot in `resolve_account_service.rb`; use a name like `keygen.internal`, or set `KEYGEN_DOMAIN` and `KEYGEN_SUBDOMAIN`.
3. Keygen forces TLS and answers plain HTTP with a 308 to `https://`. It does not terminate TLS, but it trusts `X-Forwarded-Proto: https` from RFC 1918 peers, so an internal caller needs that header rather than a TLS terminator. Without it every call redirects and reads as an empty result.

The account's public key is not exposed over the API; read it with `rails runner "puts Account.sole.ed25519_public_key"`. That keypair is the most critical secret in the system. The desktop app accepts only files signed by a key compiled into it, and that key is meant to be this account's, so losing the private half means no shipped binary accepts a new file until a release trusts a new key. Back it up out of band, separate from the Postgres dump.

## Job packs

A job pack is a job's signed data, never code: `job-pack.json` lists every file's sha256 and is signed with SurfSense's Ed25519 pack key in `job-pack.sig`, zipped with the files it lists ([contract 6](../../contracts/06-job-pack-delivery.md)). No pack is in the image or this repository ([ADR 0081](../../adr/0081-the-license-server-delivers-job-packs-from-private-releases.md)): the server reads them from a store at run time, checks each as the app will and more strictly, and serves those that pass from memory. `job_packs/source.py` says what a store is, a list of assets and a read of one, so the cache reads either store the same way.

### The store

`configured_source()` in `job_packs/catalog.py` picks one, and `shared_catalog()`, which makes the process's one catalog for it, logs once which, never the token:

- **GitHub releases** (`job_packs/github_releases.py`), when `JOB_PACKS_GITHUB_REPO` and `JOB_PACKS_GITHUB_TOKEN` are both set: a private repository that holds only releases, read with a fine-grained token limited to it, with read access to its contents. A release tagged `<id>-v<version>` carries one asset, `<id>-<version>.zip`. Drafts and prereleases are skipped; so are a tag of another shape and a release without exactly that asset, with a warning, and an asset over 50 MiB, with an error. The listing is `GET /repos/{repo}/releases?per_page=100` at API version `2022-11-28`, following the `next` link for up to 10 pages, with a warning when there are more. An asset is downloaded from its API address as `application/octet-stream`; GitHub answers with a redirect to its storage, which the server follows itself, to an `https` address only and without the token. The token goes to GitHub's API alone: a `next` link outside it fails the read, and a release whose asset has no address under it is skipped with a warning. A 401 is logged as GitHub refusing `JOB_PACKS_GITHUB_TOKEN`, a 403 with no rate left with its reset time, and another 403 or a 404 as a repository that does not exist or that the token cannot read.
- **A folder** (`job_packs/directory.py`) of zips named `<id>-<version>.zip`, `JOB_PACKS_DIR`, for tests, local runs and emergencies. It wins when set, even beside the repository settings. A relative path is taken from the working directory, `/srv/remote` in the image.

A repository without a token configures nothing and logs a warning; with no store, the route answers `503`.

### The checks

`verified_pack()` in `job_packs/verify.py` checks a zip before it is ever served, and the first failure names it:

1. At most 50 MiB (`PACK_TOO_LARGE`), a zip (`NOT_A_PACK`), and at most 1,000 members, folders counted, and 50 MiB once extracted by their declared sizes (`PACK_TOO_LARGE`).
2. Names (`BAD_PATH`): at most 255 bytes in UTF-8, checked first so no later check walks a longer name, relative POSIX paths in normal form, split as written so a lone `.` is refused too, no symlink, no two names equal without case, no character Windows cannot write (`<`, `>`, `"`, `|`, `?`, `*` or a control character), no part ending in a dot or a space or that Windows reserves (`CON`, `PRN`, `AUX`, `NUL`, `COM1` to `COM9`, `LPT1` to `LPT9`, with or without an extension), no part ending in `~` and digits before its last dot, or at its end without one, which Windows could take for another file's short name, no folder spelled two ways but for case, and no file named as a folder of another member, since neither extracts as named.
3. Every member stored or deflated, never encrypted, a folder carrying no data, with `job-pack.json` at the root (`NOT_A_PACK`) and `job-pack.sig` beside it (`PACK_NOT_SIGNED`).
4. The manifest: strict UTF-8 with no byte-order mark, JSON, and the app's manifest rules (`job_packs/manifest.py`), each part of `version` 1 to 9 ASCII digits among them, since the app sends it back as `installed_version`, which the route holds to that, except that a runner may be one the server has never heard of, since choosing a pack filters runners (`BAD_MANIFEST`, or `BAD_PATH` for a path it lists).
5. The signatures (`job_packs/signature.py`): one to eight lines of strict base64, each 64 bytes, every one verifying with a key in `PACK_PUBLIC_KEYS_HEX`, the keys the newest app compiles in (`PACK_BAD_SIGNATURE`). The app accepts a pack when any line verifies, so a key rotation can sign with the old key and the new one.
6. The files: none unlisted, none missing, every sha256 as listed (`PACK_FILE_UNLISTED`, `PACK_FILE_MISSING`, `PACK_FILE_CHANGED`).
7. `access` is `paid` (`PACK_NOT_PAID`), every job has an `entitlement` (`PACK_JOB_WITHOUT_ENTITLEMENT`), and the asset is named `<id>-<version>.zip` after its manifest (`PACK_NAME_MISMATCH`), as the GitHub store has already matched it to its tag.

Any other error while reading the archive is `NOT_A_PACK`. A zip that fails is never served and is logged at ERROR with its name and code, and the versions that passed keep being served.

### The cache

`PackCatalog` in `job_packs/catalog.py`, one per process (`shared_catalog()`), stands between the route and the store:

- It reads the store at most every `JOB_PACKS_CACHE_SECONDS`, 600 by default, and answers from memory in between. A read has 30 seconds, and requests that arrive during it wait for it rather than starting their own.
- It downloads each asset once. An asset is known by its id, update time and size on GitHub, or its name, modification time and size in a folder: a verified one is kept, a refused one is not downloaded again, and one no longer listed is dropped, so a deleted release stops being served.
- An asset that fails its checks, cannot be read as a zip at all, or is still being checked after 10 seconds, is refused and logged and never takes the others down. A check runs in a thread, which runs on to its end, but the read moves on to the other assets. A download that fails is tried again at the next read, which then comes after 60 seconds.
- When the listing fails, times out or raises anything else, it logs at ERROR, keeps serving the last good packs and tries again after 60 seconds. A copy that starts while the store fails has no packs, and answers `503` until a read succeeds or `JOB_PACKS_DIR` is set.
- The route answers with the verified bytes from memory and never redirects, so the app reaches no host but this one.

Each copy of the backend keeps its own cache and reads the store on its own, so a new version reaches apps within 10 minutes of publishing.

### Publishing

A pack is published from the maintainer's machine, where the signing key is, by `tools/publish_pack.py` in the private pack repository: it checks a sealed, signed pack with the app's checks and the server's, refuses a version that is not higher or a second id for an entitlement, zips it and runs `gh release create`. A published version never changes: a fix is a new, higher version, and every later pack with a job for an entitlement keeps the id of the first.

`python -m license.scripts.list_job_packs`, in the backend's container, reads the configured store, downloads and checks every asset, and prints a line for each job it would serve, `<id> <version>: <key> (<runner>) for <entitlement>`, one for each refused asset with its code, and one for each asset it could not download. It exits 1 when no store is set, the store cannot be read or nothing passes, and never prints the token.

### Runbook

1. **Before.** This route and the app's Jobs screen are merged to dev and released to `main`, which Coolify builds from, by hand, in about 7 minutes, and `api.surfsense.com`'s `/api/v1` is served by the Coolify application that builds `backend/` with `server/Dockerfile`. The Business setup is done: the setup script ran with the admin token, the product token is in `KEYGEN_API_TOKEN`, and `KEYGEN_POLICY_BUSINESS`, `KEYGEN_POLICY_BUSINESS_TRIAL`, `STRIPE_PRICE_LICENSE_BUSINESS` and `STRIPE_CUSTOMER_PORTAL_URL` are set.
2. **The proxy.** In Coolify, under Servers › localhost › Proxy, check that it is Traefik, which writes `X-Real-Ip`, and leave `LICENSE_CLIENT_IP_HEADER` unset. Caddy would need `x-forwarded-for`, and Cloudflare in front of the host `cf-connecting-ip`.
3. **The repository.** `gh repo create MODSetter/surfsense-job-packs --private --add-readme --description "Signed SurfSense job packs, as releases. No source."`; then turn off Issues, Wiki, Projects and Discussions, keep access to maintainers, and turn on release immutability if GitHub offers it. Nothing but releases ever goes in it.
4. **The token.** A fine-grained token named `license-server-job-packs`, owned by MODSetter, for that repository alone, with Contents read-only (Metadata read-only comes with it) and an expiry, with a reminder two weeks before; it is kept in the password manager.
5. **Coolify.** On the backend's Coolify application, add `JOB_PACKS_GITHUB_REPO=MODSetter/surfsense-job-packs` and `JOB_PACKS_GITHUB_TOKEN` as a runtime-only secret, leave `JOB_PACKS_DIR`, the cache and the rate limits at their defaults (`REDIS_URL` is optional), and redeploy, not restart.
6. **Check without a key.** `curl -s -X POST https://api.surfsense.com/api/v1/license/job-pack -H 'Content-Type: application/json' -d '{"key":"x","entitlement":"JOB_NOT_SOLD","runners":["workbook-rows/1"]}'` must answer `422` `unknown_job`; a bare `404` means the deploy lacks the route or `KEYGEN_API_TOKEN`. In the backend's Coolify terminal, `python -m license.scripts.list_job_packs` must end with "No job pack passes its checks, so none is served.", not "The job pack store cannot be read", which names what failed.
7. **Keygen.** Before the switch, run the live contract suite against CE once, `KEYGEN_INTEGRATION=1 uv run pytest license/tests/test_keygen_contract.py`, which proves `validate-key` carries a license's `jobs`.
8. **The first pack**, on the maintainer's machine, from `surfsense_local/backend` in a SurfSense checkout at the release that ships the Jobs screen: run `uv sync` in that checkout's `backend/` first, since `publish_pack.py` runs the server's checks with the packages in `backend/.venv`; check the pack's seal and signature, re-sealing and re-signing only if a file changed; run `publish_pack.py` with `--repo MODSetter/surfsense-job-packs --dry-run`, then without `--dry-run`. `list_job_packs` then names the pack, and the route serves it within 10 minutes.
9. **End to end**, with a real Business or Business trial license in the released app: add the license, choose Allow at "Allow downloading your jobs?", and Jobs shows the job ready to Run. To try the route with curl instead, put the body with the key in a file, send it with `--data @body.json`, then delete the file: a key never goes on a command line or in a URL.
10. **At the switch**, on one day and in this order: publish the app release with the Jobs screen, with `release.py`'s pin pointing the mails at it; publish the first pack; flip www's `NEXT_PUBLIC_BUSINESS_LAUNCHED`; then, with `KEYGEN_POLICY_BUSINESS_TRIAL` set and `LICENSE_TRIAL_ENABLED=TRUE`, set `LICENSE_TRIAL_BUSINESS=TRUE` and redeploy. A trial claimed at `/downloads` with your own address must bring "Your SurfSense Business 14-day trial license" with step 5, and adding it must download the job. Never earlier: trial mails would point at a missing screen, and downloads would answer `503`.
11. **Replacing the token**, before it expires: make a new one as above, replace the Coolify secret, redeploy, run `list_job_packs`, then delete the old token. A lapsed token logs "GitHub refused JOB_PACKS_GITHUB_TOKEN: it is wrong or has expired" at each read of the store, at most once a minute while requests come, and the packs in memory keep being served until the next restart.
12. **Emergency**, when GitHub or the token is down at a restart: mount Coolify persistent storage at `/srv/remote/job-packs`, copy the published zip into it, set `JOB_PACKS_DIR=/srv/remote/job-packs` and redeploy; unset it once GitHub is back.
13. **Rotating the pack signing key.** Release apps whose `PACK_PUBLIC_KEYS_HEX` holds the new key, and add it to `job_packs/signature.py`; sign packs with both keys, one line each, until the apps that trust only the old key have aged out; then sign with the new key alone and drop the old one from both lists. On a leak, drop the key from the server's list and redeploy at once, which stops delivery of the packs it signed; publish the next version of each, signed with the remaining key alone, since a published version never changes; and ship an app without the leaked key.
14. **A computer that cannot reach the server.** Support sends the published zip for the customer's job by hand, and only to a license that includes the job.

## Files

Under `backend/license/`, every setting surfsense_backend had keeping its name and meaning:

| File | Responsibility |
|---|---|
| `portal.py` | the `/api/v1` router, only with `KEYGEN_API_TOKEN`, with the memory buckets' sweep as its lifespan, and the site origins CORS lets in |
| `router.py` | the three license routes |
| `refresh_route.py` | `POST /license/refresh`, the app's renewed file by key |
| `job_packs/route.py` | `POST /license/job-pack`: the checks in the contract's order, then the zip, a `204` or a refusal |
| `job_packs/schemas.py` | the job pack request: key, job code, installed version, runners |
| `job_packs/verdict.py` | the key's validation on Keygen, and the license's `jobs` |
| `job_packs/selection.py` | which pack a license and an app get, or why none |
| `job_packs/catalog.py` | the configured store, and the packs read from it: the cache, one read at a time, the last good packs |
| `job_packs/source.py` | what a store offers: its assets, and an asset's bytes |
| `job_packs/github_releases.py` | the store on a private repository's GitHub releases |
| `job_packs/directory.py` | the store on a folder, `JOB_PACKS_DIR` |
| `job_packs/verify.py` | the checks a zip passes before it is served |
| `job_packs/manifest.py` | `job-pack.json`'s rules and safe paths, as the app reads them |
| `job_packs/signature.py` | the pack public keys, and every signature line checked against them |
| `stripe_webhook.py` | Stripe's webhook: the signature, then the event's handler |
| `stripe_client.py` | the Stripe client, and a session's metadata as a dict |
| `settings.py` | the `KEYGEN_*`, `LICENSE_*` (`LICENSE_JOB_PACK_*` and `LICENSE_CLIENT_IP_HEADER` among them), `JOB_PACKS_*`, `STRIPE_*` and license sender settings |
| `keygen.py` | the Keygen client: create, get, validate by id or key, check out, list by metadata (one page, or every page), update, suspend |
| `fresh_file.py` | a check-out only after the license validates |
| `jobs.py` | the job entitlement codes Business and its trial unlock, and a license's `jobs` read as the app reads it |
| `issue.py` | minting: derived ids, trial expiry and the Business trial, fulfilling a purchase, the file for a session |
| `checkout.py` | reading a Stripe session: email, customer, subscription, firm, plan |
| `purchase.py` | what a paid session or money returned means: claim, fulfil and mail, suspend |
| `charged_license.py` | the one license a payment paid for: by invoice and subscription, or by checkout session |
| `subscription/paid_period.py` | what a subscription paid for: the expiry it buys, its people, the invoice's subscription |
| `subscription/subscribed_license.py` | the license a subscription pays for |
| `subscription/renewal.py`, `people.py`, `lapse.py` | `invoice.paid`, `customer.subscription.updated` and `.deleted` |
| `records.py` | reading licenses back by session, email or id |
| `admin.py` | address corrections |
| `models.py` | metadata key spellings, errors and value types |
| `schemas.py` | the request and acknowledgement bodies |
| `rate_limit.py` | the two buckets per route, the address's first |
| `token_bucket.py` | the bucket on Redis, and its in-memory fallback, which forgets a bucket idle for an hour, swept every minute while the portal is served, and holds at most 100,000 |
| `client_ip.py` | the caller's address, from the one header the proxy writes (`LICENSE_CLIENT_IP_HEADER`) |
| `analytics.py` | the opt-in PostHog client |
| `release.py` | the desktop release the mail links to, through the site's download redirect |
| `funnel/channel.py` | the acquisition channel tag: validating it, reducing `client_reference_id` to it |
| `funnel/events.py` | the personless `license_trial_issued` and `license_purchased` events |
| `email/address.py` | normalizing, folding, the disposable-domain check |
| `email/deliver.py` | handing a built message to the mailer |
| `email/message.py` | subjects, bodies, attachments and sender, and the Business copy with its first-job step |
| `cohorts/keygen_licences.py` | every licence, split into trials and purchases |
| `cohorts/stripe_purchases.py` | a purchase's checkout and customer addresses, and full refunds, from Stripe |
| `cohorts/plugin_host_first_seen.py` | the plugin host's first-seen day per licence |
| `cohorts/email_kind.py` | company, free mail or school, by domain |
| `cohorts/weekly.py` | trials grouped by ISO week and joined to plugin use and payment |
| `cohorts/published_figures.py` | a cohort's figures with small cells withheld, and the kinds that would give them away |
| `cohorts/markdown_table.py`, `cohorts/posthog_events.py` | the printed table and the weekly events |
| `cohorts/models.py` | the trial and purchase records, held in memory only |

One handler outside the folder belongs to the portal: the one in `backend/server/app.py` that answers a refused `/api/v1` request with a `422` that leaves out its input ([routes](#routes)).

Five scripts sit in `backend/license/scripts/`, run as `python -m license.scripts.<name>` in the backend's container, or from `backend/` with `uv run`. `issue_enterprise_license.py` issues an invoiced license without Stripe and prints the file, and also mails it with `--mail`. `correct_license_email.py` repairs a mistyped purchase address, and `license_cohorts.py` prints the [cohort report](#cohort-report), both below. `list_job_packs.py` names the packs the configured store would serve and the assets it refuses ([publishing](#publishing)).

`setup_business_policies.py` creates the Business policies and the job entitlements, run with the admin token in `KEYGEN_API_TOKEN`:

```bash
python -m license.scripts.setup_business_policies --dry-run
python -m license.scripts.setup_business_policies --product-token
```

It reads the live trial, individual and team policies for their product and signing scheme and writes nothing to them. It finds its own policies by `metadata.surfsensePolicy` among the product's, so a rename does not make a second run create them again; creates whichever of the two is missing, each entitlement in `jobs.py` that is missing, and attaches the missing ones to both. It refuses, before any write, when the live policies span products or one of its policies has been made strict. It prints the `KEYGEN_POLICY_BUSINESS` and `KEYGEN_POLICY_BUSINESS_TRIAL` lines, and with `--product-token` a new product token, shown once. A second run creates nothing, and a job added to `jobs.py` is created and attached by the next run.

## Pages

In `www`, all public routes:

- `/license/success` is where Stripe returns the buyer. It downloads the file once on mount, since that first request may be what creates the license, then leaves retries to a button rather than looping. A 404 reads as "payment is still settling, press again", never "you have no license". The first file saved for a checkout fires confetti; a `localStorage` flag per `session_id` keeps a retry or a reload quiet in that browser.
- `/license` has only the resend form. Resend can never say "no license found", so its success copy tells the user to check spam and use the exact address they paid with.
- The trial form is on `/downloads`, beside the installers a license file is useless without. It sends the visitor's channel tag with the email and captures `license_trial_requested` with the outcome (`sent`, `already_claimed`, `refused` or `error`) and the channel, never the address. A sent trial fires confetti, and an "Already have a license? Resend it" line under the form links to `/license`.
- Both forms are one email pill (`www/features/license/license-forms.tsx`), and a successful send links on to `/license/activate`. Confetti (`www/features/celebration/`) loads only when it fires and is skipped under reduced motion.
- `/pricing/individual` sits between the pricing card and the Stripe Payment Link (`NEXT_PUBLIC_STRIPE_LICENSE_INDIVIDUAL_URL`): what the licence unlocks, the renewal, what happens after paying, the refund. Its Continue to checkout button appends `client_reference_id=<channel>` and captures `checkout_started` by beacon. The channel is the first-touch `?ref` code or `utm_source` the site already records, else the referring site's domain, else `direct` (`www/features/funnel-attribution/`), and never a person or browser id. The Payment Link's after-payment redirect must be `https://www.surfsense.com/license/success?session_id={CHECKOUT_SESSION_ID}`. The page says the confirmation page downloads the file and that nothing charges again, while the live Payment Link sells a yearly subscription; a paid renewal now extends the same license ([subscriptions](#subscriptions)).
- `/license/activate` is the activation guide the mail links to.

The pages state two dead ends plainly. An enterprise license is one file sent only to the buying address, so a colleague asks the buyer to forward it. A lost or mistyped inbox has no self-serve path, because a form that mailed a license to a newly typed address would be a way to steal one.

## Support corrections

A buyer who mistyped the checkout email and also closed the success page before saving the file reaches support. Support asks for proof only the payer holds, the charge id from the bank statement or the last four digits, amount and date, finds the charge in Stripe and runs:

```bash
python -m license.scripts.correct_license_email --session cs_... --email real@buyer.com --mail
```

The script matches on the payment, never on how alike two addresses look: `checkoutSessionId` names exactly one license, and the script refuses when two carry it. It prints the record, asks for confirmation unless `--yes` is passed, rewrites the stored `email`, and then mails a fresh file with `--mail` or prints it. Rewriting the address is the point, because resend looks customers up by it; a typo left in Keygen makes every future download another ticket. A buyer who lost the inbox takes the same path. Someone who fools support gets one license that can be suspended, a risk accepted over identity checks.

A trial has no payment to prove, so the anchor is the address itself: support asks which exact address the trial was requested with and runs `--trial-email typo@... --email real@... --mail` in place of `--session`. The lookup filters on that address as typed and on its folded `trialKey`, so it finds only a trial issued to exactly that address, never a lookalike and never a paid licence there, and it refuses when two match. Someone who knows another person's exact address could have that trial repointed to their own inbox. They gain a free trial that expires and can be suspended, and the correction moves `trialKey` with the address, so the owner can claim a trial again; that risk is accepted as for purchases.

## Cohort report

`scripts/license_cohorts.py` shows how trials turn into plugin use and sales, from the records Keygen and Stripe already hold, without touching the app:

```bash
python -m license.scripts.license_cohorts            # print the table
python -m license.scripts.license_cohorts --posthog  # and send it to PostHog
```

It reads every licence through `iter_licenses()`, which pages through Keygen, since `list_licenses()` sends one request and stops at 100. A licence whose `plan` is `trial` is a trial, keyed by its folded `trialKey`; any other is a purchase, dated by its creation. With `STRIPE_SECRET_KEY` set it retrieves each purchase's checkout session, read-only, so a restricted key that reads Checkout Sessions, Customers, PaymentIntents and Charges is enough: that adds the address typed at checkout and the Stripe customer's address, both folded, and marks a full refund. Without Stripe a suspended licence counts as refunded, since only a full refund suspends one. With `PLUGIN_HOST_ADMIN_URL` and `USAGE_ADMIN_TOKEN` set it reads the plugin host's `GET /admin/usage/first-seen`, `{"licences": {"<licence id>": "YYYY-MM-DD"}}`, with the token as a bearer.

A trial matches the first purchase on or after its creation that carries its folded address. For each ISO week of trial creation, and for all weeks together, the table shows:

- trials issued;
- the shares at a company domain, a free-mail domain (a static list in `cohorts/email_kind.py`) and a school (`.edu`, `.ac.<country>`, `k12`), which misses universities on plain domains;
- the share later seen on the plugin host, and the median days to that first call;
- the shares paid within 30 and 60 days, marked open while some trial in the row is younger than the window, and the median days to pay;
- refunds.

No address, domain, licence id or key is printed or sent. A count under 5 prints as `<5` and a median of fewer than 5 values as `n<5`. Other cells are withheld so that no `<5` can be worked out, and print as `x` whatever their own value, since a mark saying a cell is 5 or more would pin a small one beside it. The three kinds add up to a row's trials, give or take an unreadable address, so when any kind is under 5 all three print as `x`: withholding only the small ones would still let the trials and the kinds shown pin them. The All row is the weeks' sum, so each count a week withholds (trials, a kind, plugin use, paid within 30 or 60 days, refunds) prints as `x` in the All row too; with few trials, and the current week still filling, that is most columns most of the time. `--posthog` sends the same weekly figures, withheld ones as null and `withheld_to_protect` naming those that print as `x`, as one personless `license_cohort_weekly` event per week through `POSTHOG_API_KEY`; each run sends every week again, so read the latest. The addresses were given to receive a licence, so no single row is acted on, such as mailing a lapsed trial.

`test_keygen_pages.py` covers reading every page. `test_cohort_email_kind.py`, `test_cohort_weekly.py`, `test_cohort_sources.py` and `test_cohort_publishing.py` cover the cohort report's domain classes, the join, the three readers with Keygen, Stripe and the plugin host faked, and the withheld cells, including those withheld so that a small one cannot be worked out, and `test_license_cohorts_script.py` checks that the printed report and its events carry no address or licence id.

## Tests

Under `backend/license/tests/` and `backend/mailer/tests/`, run from `backend/` with `uv run pytest license mailer`. `test_funnel_events.py` covers the channel tag rules and the purchase event: its exact properties, nothing personal in it, and one event when the webhook and the success page both fulfil. `test_issue.py` covers Keygen payload shapes, metadata filter syntax, the CE headers, trial expiry, address folding, the disposable-domain check, plan resolution, derived ids and both duplicate-id answers; `test_message.py` and `test_release.py` cover the mail, the Individual purchase mail's promises, which no Business mail makes, the first-job step in the Business purchase and trial mails alone, and the mail's pinned redirect links; `test_mail_guard.py` covers the mail check both POST routes run before Keygen; `test_trial_disposable.py` covers the trial's refusal of a disposable address before Keygen; `test_trial_correction_lookup.py` covers the support lookup of a trial by its exact address. `backend/mailer/tests/` covers the SMTP error mapping, MIME shape, senders and configuration checks, and its `test_smtp_contract.py` sends through a real SMTP conversation against Mailpit when `SMTP_INTEGRATION=1`. `test_license_routes.py` drives the three routes over HTTP with Keygen faked at its transport, so the code under them runs as written, and the mailer faked at the router: resend's one answer for every outcome, asserted from the mailer side, including a license that is only suspended, and its 503 when mail is off before any lookup; each trial outcome, never with the file in the body, and a tagged address refused once the folded one holds a trial; `license_trial_issued` with only the channel, a bad channel dropped, and no event for a trial not issued; the success page's file and its 404; both rate-limit buckets biting, and a limit of zero turning one off. `test_keygen_contract.py` runs the client against a real Keygen when `KEYGEN_INTEGRATION=1`, proving the metadata keys the app writes are the ones it filters on, that a key with another word answers an empty list, and that `validate-key` answers a license's `jobs`. `test_stripe_webhook.py` posts events signed as Stripe signs them: a license purchase creates its license in Keygen, and an event signed with another secret is refused. The Business and subscription tests post signed events too, with Keygen and Stripe both faked at their transports (`tests/billing_harness.py`, `tests/stripe_fake.py`, the real `StripeClient` over a fake HTTP client) and the mail built for real and caught at the mailer. `test_business_purchase.py` covers a Payment Link's Business checkout: one license on the business policy with the people, firm, jobs and subscription, its first period plus 30 days, a validation before the `ttl: null` check-out, the Business mail, and the success page before the webhook. `test_subscription_lifecycle.py` covers a renewal on the same key and its mail, a retried one changing nothing, the first invoice before the checkout, people confirmed at renewal, a suspended license extended but not mailed, an Individual subscription sold before `stripeSubscriptionId` renewing on its own key, a seat change moving only `maxUsers`, a period advanced before payment extending nothing, and an ended subscription left to lapse. `test_money_returned.py` covers a refunded or disputed year suspending its subscription's license and no other, a proration or partial refund suspending nothing, a one-time payment with no Stripe customer traced, and an older Individual subscription traced through its checkout. `test_refresh_route.py` covers the refresh's file, its validation first, a suspended license refused, a lapsed one served, an unknown key, the key kept out of bucket names, both buckets and Keygen down. `test_business_trial.py` covers the trial switch off and on, an earlier trial not using up the Business one, and the switch without its policy. `test_setup_business_policies.py` covers the setup script against a faked Keygen account: both policies non-strict and joined to the live product, a second run creating nothing, a new job attached, the live policies only read, the refusals, and the product token only when asked. `test_license_routes.py` also covers a refunded purchase's success page and every check-out following its license's validation. `test_token_bucket.py` checks on a real Redis, CI's or a local `redis-server`, that two copies of the backend draw on one bucket; without one it skips. [`server/tests/`](../../../backend/server/tests/) check that the routes, the job pack route among them, are served only with `KEYGEN_API_TOKEN`, that the served portal drops a caller's rate-limit counts an hour after its last request with no request after it, that a refused portal body is never echoed while one refused elsewhere keeps FastAPI's own answer, that CORS answers the site, and that no `/docs` or `/openapi.json` is published.

The job pack tests build packs signed by a test key (`tests/job_pack_samples.py`), fake GitHub at its transport (`tests/github_fake.py`), and reach the route through the backend's own app over a faked Keygen (`tests/job_pack_portal.py`, behind `conftest.py`'s `pack_portal` fixture), so the 422 handler answers as it does in production. `test_job_pack_verify.py` covers a sealed, signed pack accepted, the signed bytes being the app's, an unknown runner, a second trusted signature, eight trusted lines and a directory entry accepted, the first failing check naming the refusal, and every refusal by its code, Windows names and characters, a lone `.`, a name past 255 bytes in UTF-8, one 5,000 folders deep among them, a Windows short name of another file or folder, a file and a folder of one name in either order, a folder entry among them, a folder spelled two ways, folders counted among the 1,000 members, a folder carrying data, a version part of ten digits or with a digit that is not ASCII, an encrypted member, a corrupt deflate stream, JSON nested too deep and a ninth signature line among them, and that no test key is trusted in production. `test_job_pack_selection.py` covers versions compared as numbers, the entitlement and runner filters, a pack holding a job the license lacks withheld, and when the installed version is current. `test_job_pack_catalog.py` covers one listing per TTL, one download per asset, one read for concurrent requests, paging, the headers, the redirect followed without the token and a plain-http one refused, a next page or an asset outside GitHub's API never asked, the store's client following no redirect on its own, the releases skipped, a tag or a zip name whose version has a digit that is not ASCII among them, a broken or unreadable release never served and never taking the others down, an unexpected error refusing only its release, a check past its deadline refusing only its release, the read's deadline, a download past 50 MB cut off and an asset listed over it never downloaded, the last good packs kept while GitHub fails, the one-minute retry, a cold start while failing, a refused token logged without the token, a deleted release dropped, the folder store and a missing folder, no store, `JOB_PACKS_DIR` winning, a repository without a token configuring nothing, and one catalog per configured store. `test_job_pack_route.py` drives the route over HTTP with Keygen faked: every answer and code in the contract's order, `EXPIRED` refused while the refresh still serves the file, the Business trial served, the license checked before any pack is read, a pack holding a job the license lacks refused as `pack_not_covered`, a malformed body's `422` echoing nothing, the `204` and its headers, a version the app could not send back never served, nor one in digits that are not ASCII, which no header carries, the runner filter and its `409`, each `503`, the key in no bucket name or log, both buckets, and the refresh's buckets apart from the route's. `test_job_pack_contract.py` checks that contract 6's sample passes the checks and is served byte for byte from a folder store. `test_memory_buckets.py` covers a memory bucket forgotten after an idle hour, the cap on their number, and a caller the address bucket refuses spending no key bucket; `test_client_ip.py` covers the address taken from the proxy's header, a forged `CF-Connecting-IP` ignored, another header named, the socket peer without the header and the one warning naming it, and an empty setting taking the socket peer with no warning; `test_jobs.py` covers `jobs` read as the app reads it; and `test_list_job_packs_script.py` covers the script's lines, its exit codes and the token never printed.

## Known gaps

- The cohort report has not run against production Keygen or Stripe.
- The Keygen contract test has not yet run against a live Keygen; it skips without `KEYGEN_INTEGRATION=1` and credentials. Its cases for validation, a suspended license's check-out, an expiry moved on the same key and `validate-key` answering a license's `jobs` have not run either, and neither has the setup script against Keygen CE.
- The app does not call `POST /license/refresh` yet, so a renewal reaches an Individual or Business user only by the renewal mail until it does.
- No app on dev calls `POST /license/job-pack` yet.
- A dispute won later leaves its license suspended until support reinstates it.
- A job added to `jobs.py` reaches new licenses and the policies' entitlements, but the `jobs` already written on existing licenses keep the old list, so the job pack route refuses them the new job.
- The GitHub store has not read the real releases repository, and no pack is published; its tests fake GitHub at the transport.
- A computer that cannot reach the license server gets a pack file only from support, by hand.
- `scripts/issue_enterprise_license.py` issues no Business license with `jobs`, so a license it issues gets no pack.
- Individual licenses are not converted to Business Solo (ADR 0079): nothing moves one to a Business policy and writes its `jobs`, so the job pack route refuses it every job.
- Nothing warns before `JOB_PACKS_GITHUB_TOKEN` expires; once it has, the refusal is only logged.
- Each copy of the backend keeps its own pack cache, and without `REDIS_URL` its own rate-limit counts too, so every copy allows the full limits.
- Without `REDIS_URL`, 100,000 new addresses within an hour push the least recently refilled memory buckets out, so those callers start again with full ones; and a caller that changes its IPv6 address on each request gets a fresh address bucket every time, though the key's bucket still holds.
- Nothing detects a license key shared beyond its firm, such as one key asking from many networks.
- The Business trial's two hidden rules in ADR 0079, Gmail dots folded into one address and at most two trials a year per company domain, are not built.
- Nothing checks the Payment Links' settings. Their after-payment redirect, the Business price's quantity limits and its `firm` field are set by hand in Stripe, and PostHog's 15 checkout clicks against 1 success page view in the 30 days to 21 Oct 2026 suggest the Individual link's redirect is not set.
