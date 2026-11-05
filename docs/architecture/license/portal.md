# License portal

The one [backend](../backend.md) sells, delivers and re-delivers the desktop app's license file with no accounts and no license table. Stripe and Keygen are the system of record: every search is a filter over Keygen license metadata, and the one direct read is by a derived id, and the license routes take no session, read no user table and touch no Postgres. Control of an inbox replaces the login, because a license is only ever mailed to the address it is registered to. Where having no table would cost a guarantee, the code moves the guarantee into Keygen instead of adding a table.

**Code:** [`backend/license/`](../../../backend/license/), [`backend/mailer/`](../../../backend/mailer/), [`www/app/(home)/license/`](../../../www/app/\(home\)/license/)
**Decisions:** [ADR 0024](../../adr/0024-portal-without-accounts.md), [ADR 0019](../../adr/0019-offline-licenses.md), ADR 0080 (one Business license, priced per person; on the `docs/business-license` branch)

What the routes produce is [contract 1](../../contracts/01-license-file.md); the [desktop app](app.md) consumes it.

## Routes

All under `/api/v1`, unauthenticated, FastAPI routers that [`portal.py`](../../../backend/license/portal.py) groups and the [backend's](../backend.md) app includes only when `KEYGEN_API_TOKEN` is set. The backend's CORS lets in `NEXT_FRONTEND_URL`, its www or bare twin and localhost, exposing `Content-Disposition`:

| Route | Answers |
|---|---|
| `GET /license/file?session_id=` | the `.lic` for that checkout session, or 404 |
| `POST /license/resend` `{email}` | 200 with the same body whatever it found |
| `POST /license/trial` `{email, channel?}` | 200 once the trial is mailed |
| `POST /license/refresh` `{key}` | the license's current `.lic`, for the app after a renewal |
| `POST /stripe/webhook` | purchases, renewals, seat changes, ended subscriptions, refunds and disputes |

Resend and trial validate `email` as an email address and answer 422 for anything else. The trial's optional `channel` is the site's acquisition tag ([funnel events](#funnel-events)); it is kept only when it matches `^[a-z0-9_-]{1,40}$` and is dropped otherwise, never refused, so a bad tag cannot cost anyone a trial.

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

`resolve_license_plan()` reads the plan two ways, so a Payment Link and an API-created session both work. Session metadata with `purchase_type: license` comes first (`plan` of `individual`, `team` or `business`, and `quantity` for team and business); otherwise the line item's price ID is matched against `STRIPE_PRICE_LICENSE_INDIVIDUAL`, `STRIPE_PRICE_LICENSE_TEAM` and `STRIPE_PRICE_LICENSE_BUSINESS`, with the line item quantity as the team's seats or the Business license's people, in `maxUsers`. Business is one yearly price per person, $60 a year (decided 4 Nov 2026), so its quantity is the number of people. Webhook payloads carry no line items, so a Payment Link purchase costs one extra Stripe call. The site sells Individual through a Payment Link and no longer sells Team; the backend still supports it, and `scripts/issue_enterprise_license.py` issues team licenses by hand.

### Subscriptions

Business renews every year on the same key (ADR 0080), and the Individual Payment Link has sold yearly subscriptions too, so a license sold on a subscription follows it. `subscription/` holds the rules:

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
| `jobs` | Business and its trial | the app (contract 1): which job plugins the license unlocks |

Keygen snake-cases metadata keys when it stores them and when it filters on them, and camelCases them in responses ([`jsonapi.rb`](https://github.com/keygen-sh/keygen-api/blob/v1.7.2/config/initializers/jsonapi.rb#L5-L11), [`license.rb`](https://github.com/keygen-sh/keygen-api/blob/v1.7.2/app/models/license.rb#L337-L338)), so `checkoutSessionId` and `checkout_session_id` are one key. A key with a different word is what goes wrong: it returns an empty list rather than an error, which reads as "no license". The spellings live in `app/license/models.py`, except that `create_license()` in `keygen.py` writes `plan` and `email` as literals.

Certificates are never stored. Every delivery, whether success page, purchase or renewal mail, resend or the app's refresh, checks out a fresh file with `{"meta": {"ttl": null}}`, so two files for one license differ in `meta.issued` and share a key. `ttl: null` matters because the app keeps a file until it imports a newer one, and Keygen's default 30-day TTL would kill every file a month after purchase.

Every check-out follows an unscoped validation (`fresh_file.py`): `POST /licenses/{id}/actions/validate`, or `validate-key` for the refresh, and a file only when Keygen answers `VALID` or `EXPIRED`. Keygen checks no license status when a product or admin token checks a file out, so without it a refunded, suspended license would still get a fresh file from the success page. `EXPIRED` passes because the file carries the expiry the app already shows, and a lapsed trial's resend has always been answered. Unscoped, because the server names no machine or fingerprint and no policy of ours requires a scope. The server creates no machines.

Each plan has its own policy, and `jobs.py` lists the job entitlement codes, `JOB_QUESTIONNAIRE` first: the setup script attaches each to both Business policies, so Keygen holds them for a server-side check, and every Business license and trial copies them into `jobs`, which the app reads offline.

| Policy | Setting | Made by |
|---|---|---|
| trial, individual, team | `KEYGEN_POLICY_TRIAL`, `_INDIVIDUAL`, `_TEAM` | by hand, live; never edited or made strict |
| business | `KEYGEN_POLICY_BUSINESS` | the setup script: 395 days, the fallback for a license made without an expiry |
| business-trial | `KEYGEN_POLICY_BUSINESS_TRIAL` | the setup script: 14 days |

The live trial, individual and team policies are never edited or made strict: the plugin host accepts only `VALID`, and a strict policy answers `NO_MACHINE` for every key on it, which would lock all of them out. The setup script makes both Business policies non-strict and floating with no machine cap, since Business counts people, not devices (ADR 0080), with the live policies' signing scheme, so their files carry the `alg` the app accepts.

## Idempotency without a table

The Keygen license id is derived, not assigned: `uuid5` of a fixed namespace and `stripe:<checkout session id>` for a purchase, `trial:<folded email>` for a trial, or `business-trial:<folded email>` for the Business trial. When the webhook and the success page fulfil one payment at the same moment, both create the same id and Keygen refuses the second, with `422 ID_CONFLICT` when the first is already committed or a bare `409` when both are in flight, which the client confirms by fetching the id. For a purchase the loser reads the winner's license and delivers that; for a trial it answers 409. There is no lock and no table, and a second fulfilment cannot mint a second license; this replaces the earlier design of a Keygen lookup under a short Redis lock.

Only the id is derived. The license key stays Keygen-generated, because it is the bearer credential contract 2 sends to the scraper API and must be unguessable. The namespace is a constant rather than configuration, because changing it changes every derived id.

A trial has two guards. The derived id is the constraint that settles simultaneous claims; `trialKey` is a mutable index, so correcting an address can move it, which an id fixed at creation cannot follow.

## Email addresses

Delivery uses the address as typed, trimmed and lowercased. Deduplication, meaning the trial check and the per-email rate limit, also strips a `+tag` from the local part. `user+surfsense@gmail.com` is a real address the buyer may want the file at, so delivery must not fold it, but plus-tagging is the cheapest trial farm, so the trial check must. Dots are not folded: that is Gmail's rule, and applying it everywhere would collide distinct addresses at other providers. A trial stores both forms, `email` as typed and `trialKey` folded.

The trial's disposable check reads only the domain. The list is the community [disposable-email-domains](https://github.com/disposable-email-domains/disposable-email-domains) list, installed as the `disposable-email-domains` package, plus three domains our earlier hand-kept list refused and it does not carry; `LICENSE_DISPOSABLE_EMAIL_DOMAINS` adds more per deployment. The domain and every domain above it short of the TLD are looked up, because the list names registrable domains and a disposable service can mint any subdomain under one. The lookup uses punycode, the spelling the list is written in, since `EmailStr` hands the route Unicode even when punycode was typed. The package is pinned in `uv.lock`, so the list changes only with a reviewed bump, `uv lock --upgrade-package disposable-email-domains`; upstream publishes most days. A unit test fails such a bump if it would refuse a mainstream provider.

## Rate limits

Each POST takes a token from two buckets through a Redis token bucket on `REDIS_URL` (`token_bucket.py`), which falls back to per-process memory when Redis is down or unset rather than failing closed:

| Bucket | Default per hour |
|---|---|
| `license:<route>:ip:<ip>` | 10 (`LICENSE_RATE_LIMIT_IP_PER_HOUR`) |
| `license:<route>:email:<folded>` | 5 for resend, 3 for trial (`LICENSE_RESEND_RATE_LIMIT_PER_HOUR`, `LICENSE_TRIAL_RATE_LIMIT_PER_HOUR`) |
| `license:refresh:ip:<ip>` | 60 (`LICENSE_REFRESH_RATE_LIMIT_IP_PER_HOUR`) |
| `license:refresh:key:<sha256 of the key>` | 30 (`LICENSE_REFRESH_RATE_LIMIT_PER_HOUR`) |

The refresh gets more room than resend and trial because a firm's people share one key and often one address. The client IP comes from `get_real_client_ip()`, which prefers `CF-Connecting-IP`, then `X-Real-IP`, then the first `X-Forwarded-For` entry. The limits also bound mail spend and check-out load, since one resend is one check-out per license. A limit of zero turns its bucket off.

## Mail

[`backend/mailer/`](../../../backend/mailer/) is a port with one transport: `protocol.py` holds the `Mailer` protocol, the frozen `OutboundEmail` and `Attachment` payloads and the two errors; `factory.py` builds the mailer; `smtp.py` sends. The connection is deployment-wide (`SMTP_*`, read by `settings.py`), not license-specific, and each feature stamps its own sender on its messages. SMTP is the transport because every transactional provider speaks it, Resend, Postmark, SendGrid, Mailgun, SES and Brevo among them, so choosing a vendor is filling in host, port, username, password and a From address. The sender is stdlib (`email.message` and `smtplib` through `asyncio.to_thread`), one connection per send, and adds no dependency.

- `SMTP_ENABLED` defaults to false, and there is no pretend-to-send mode. Both POST routes check it first and answer 503, because a resend that always answers 200 over a mailer that silently drops mail would make a broken deployment look like a working one. The same check builds the mailer, so a bad `SMTP_*` setting also answers 503, before any Keygen call. Failing at startup instead would take every route down over a mail setting.
- `SMTP_SECURITY` is explicit, `starttls` by default, `tls` or `none`, never guessed from the port. `none` is refused when a username is set, so credentials never cross in the clear; without one it only logs a warning for a non-loopback host.
- Every send failure maps to one of two errors; a configuration error is neither: a bad setting raises `ValueError` when the mailer is built, which the routes turn into the 503 above. `MailerUnavailableError` covers connect failures, timeouts, 4xx replies, authentication failures and a refused sender, all ours to fix. `MailerRejectedError` is a permanent 5xx refusal during the conversation, of the recipient or of the message. A hard bounce arrives after a 250 accept, so trial promises "sent", never "delivered".
- `OutboundEmail.idempotency_key` is carried and ignored by SMTP, so a future API transport can dedupe retries without changing any caller.

`email/message.py` builds the four license messages, `purchase`, `resend`, `trial` and `renewal`, sent from `SMTP_LICENSE_FROM` or else `SMTP_FROM`, with `SMTP_LICENSE_REPLY_TO`. The file travels as `surfsense.lic`, numbered when one resend carries several, typed `application/octet-stream` so no mail client renders it inline and mangles its line endings. The install steps link each platform's installer through the site's download redirect, `https://www.surfsense.com/downloads/<platform>?src=email&v=<tag>`, with the tag pinned in `release.py`. The `v` keeps a mail already sent naming the build it was sent for, and the redirect counts the downloads mail produces ([updates](../updates.md#download-links)).

A Business license or trial gets its own copy of each, chosen by `BusinessCopy.of()` for a license on the business plan or one that lists `jobs`, and a resend takes it when any of its files is one. The Individual purchase mail promises that the app never contacts a license server and that the file works on every machine; neither holds for Business, whose renewed file the app fetches and which counts people, so the Business copy says neither. It names the firm and how many people the license covers, says it renews every year on the same key until cancelled, and gives `STRIPE_CUSTOMER_PORTAL_URL`, the customer portal's login link, for adding or removing people and cancelling, or says to reply when that is unset; SurfSense still has no accounts. The Business trial says only new job runs stop when it expires. The renewal mail, sent for every plan, carries the renewed file and asks for it to be imported; the Individual copy of it is the only way that renewal reaches the app.

## Keygen

Production runs a self-hosted Keygen CE. Keygen Cloud bills per active licensed user and counts a check-out as activity, and here every delivery, trials included, is a check-out. `keygen.py` talks to `KEYGEN_API_URL`, or to Keygen Cloud when that is unset; when `KEYGEN_HOST` is set it sends that name as `Host` and adds `X-Forwarded-Proto: https`. `KEYGEN_ACCOUNT_ID`, `KEYGEN_API_TOKEN` and the five `KEYGEN_POLICY_*` variables mean the same on either.

`KEYGEN_API_TOKEN` is a product token for the product every policy belongs to, and the admin token stays offline. A product token creates, reads, updates, validates, checks out and suspends its own product's licenses and creates its policies, which is all the server does; it cannot create entitlements or product tokens, so the setup script runs once with the admin token in `KEYGEN_API_TOKEN`. A product token lists only its own product's licenses, and a list that misses a license reads as "no license", so the setup script refuses when the live policies span products. CE is not a service in `docker/docker-compose.yml`; its web and worker images are in [`docker/keygen/`](../../../docker/keygen/).

Three things break a CE instance's first boot or first call:

1. Setup needs four secrets, `SECRET_KEY_BASE`, `ENCRYPTION_DETERMINISTIC_KEY`, `ENCRYPTION_PRIMARY_KEY` and `ENCRYPTION_KEY_DERIVATION_SALT`. Given those plus `KEYGEN_ACCOUNT_ID`, `KEYGEN_ADMIN_EMAIL`, `KEYGEN_ADMIN_PASSWORD`, `KEYGEN_EDITION=CE` and `KEYGEN_MODE=singleplayer`, `setup` runs non-interactively.
2. `KEYGEN_HOST` must be a dotted name with a parseable eTLD+1. A single label, `localhost` or a bare compose service name, crashes boot in `resolve_account_service.rb`; use a name like `keygen.internal`, or set `KEYGEN_DOMAIN` and `KEYGEN_SUBDOMAIN`.
3. Keygen forces TLS and answers plain HTTP with a 308 to `https://`. It does not terminate TLS, but it trusts `X-Forwarded-Proto: https` from RFC 1918 peers, so an internal caller needs that header rather than a TLS terminator. Without it every call redirects and reads as an empty result.

The account's public key is not exposed over the API; read it with `rails runner "puts Account.sole.ed25519_public_key"`. That keypair is the most critical secret in the system. The desktop app accepts only files signed by a key compiled into it, and that key is meant to be this account's, so losing the private half means no shipped binary accepts a new file until a release trusts a new key. Back it up out of band, separate from the Postgres dump.

## Files

Under `backend/license/`, every setting under surfsense_backend's name and meaning:

| File | Responsibility |
|---|---|
| `portal.py` | the `/api/v1` router, only with `KEYGEN_API_TOKEN`, and the site origins CORS lets in |
| `router.py` | the three license routes |
| `refresh_route.py` | `POST /license/refresh`, the app's renewed file by key |
| `stripe_webhook.py` | Stripe's webhook: the signature, then the event's handler |
| `stripe_client.py` | the Stripe client, and a session's metadata as a dict |
| `settings.py` | the `KEYGEN_*`, `LICENSE_*`, `STRIPE_*` and license sender settings |
| `keygen.py` | the Keygen client: create, get, validate by id or key, check out, list by metadata (one page, or every page), update, suspend |
| `fresh_file.py` | a check-out only after the license validates |
| `jobs.py` | the job entitlement codes Business and its trial unlock |
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
| `rate_limit.py` | the two buckets per route |
| `token_bucket.py` | the bucket on Redis, and its in-memory fallback |
| `client_ip.py` | the caller's address behind Cloudflare and the proxy |
| `analytics.py` | the opt-in PostHog client |
| `release.py` | the desktop release the mail links to, through the site's download redirect |
| `funnel/channel.py` | the acquisition channel tag: validating it, reducing `client_reference_id` to it |
| `funnel/events.py` | the personless `license_trial_issued` and `license_purchased` events |
| `email/address.py` | normalizing, folding, the disposable-domain check |
| `email/deliver.py` | handing a built message to the mailer |
| `email/message.py` | subjects, bodies, attachments and sender, and the Business copy |
| `cohorts/keygen_licences.py` | every licence, split into trials and purchases |
| `cohorts/stripe_purchases.py` | a purchase's checkout and customer addresses, and full refunds, from Stripe |
| `cohorts/plugin_host_first_seen.py` | the plugin host's first-seen day per licence |
| `cohorts/email_kind.py` | company, free mail or school, by domain |
| `cohorts/weekly.py` | trials grouped by ISO week and joined to plugin use and payment |
| `cohorts/published_figures.py` | a cohort's figures with small cells withheld, and the kinds that would give them away |
| `cohorts/markdown_table.py`, `cohorts/posthog_events.py` | the printed table and the weekly events |
| `cohorts/models.py` | the trial and purchase records, held in memory only |

Four scripts sit in `backend/license/scripts/`, run as `python -m license.scripts.<name>` in the backend's container, or from `backend/` with `uv run`. `issue_enterprise_license.py` issues an invoiced license without Stripe and prints the file, and also mails it with `--mail`. `correct_license_email.py` repairs a mistyped purchase address, and `license_cohorts.py` prints the [cohort report](#cohort-report), both below.

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
- `/pricing/individual` sits between the pricing card and the Stripe Payment Link (`NEXT_PUBLIC_STRIPE_LICENSE_INDIVIDUAL_URL`): what the licence unlocks, the renewal, what happens after paying, the refund. Its Continue to checkout button appends `client_reference_id=<channel>` and captures `checkout_started` by beacon, with `plan: individual`. The channel is the first-touch `?ref` code or `utm_source` the site already records, else the referring site's domain, else `direct` (`www/features/funnel-attribution/`), and never a person or browser id. The Payment Link's after-payment redirect must be `https://www.surfsense.com/license/success?session_id={CHECKOUT_SESSION_ID}`. The page says the confirmation page downloads the file and that nothing charges again, while the live Payment Link sells a yearly subscription; a paid renewal now extends the same license ([subscriptions](#subscriptions)).
- `/license/activate` is the activation guide the mail links to.
- Business waits behind `NEXT_PUBLIC_BUSINESS_LAUNCHED` (`www/features/business-launch/`), off until the release that ships the first paid job. Off, every page above reads as it does today and `/pricing/business` is a 404. On, `/pricing` lists Free, Business and Enterprise; `/pricing/business` sits between the Business card and its Payment Link (`NEXT_PUBLIC_STRIPE_LICENSE_BUSINESS_URL`, a yearly recurring price whose after-payment redirect is the same `/license/success` address), states the yearly renewal above its button, and captures `checkout_started` with `plan: business`; `/pricing/individual` redirects to it, permanently; and the trial form, `/license/activate` and `/license/success` describe the 14-day trial of the job and a license that renews, with no line saying it works on every computer.

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

Under `backend/license/tests/` and `backend/mailer/tests/`, run from `backend/` with `uv run pytest license mailer`. `test_funnel_events.py` covers the channel tag rules and the purchase event: its exact properties, nothing personal in it, and one event when the webhook and the success page both fulfil. `test_issue.py` covers Keygen payload shapes, metadata filter syntax, the CE headers, trial expiry, address folding, the disposable-domain check, plan resolution, derived ids and both duplicate-id answers; `test_message.py` and `test_release.py` cover the mail and its pinned redirect links; `test_mail_guard.py` covers the mail check both POST routes run before Keygen; `test_trial_disposable.py` covers the trial's refusal of a disposable address before Keygen; `test_trial_correction_lookup.py` covers the support lookup of a trial by its exact address. `backend/mailer/tests/` covers the SMTP error mapping, MIME shape, senders and configuration checks, and its `test_smtp_contract.py` sends through a real SMTP conversation against Mailpit when `SMTP_INTEGRATION=1`. `test_license_routes.py` drives the three routes over HTTP with Keygen faked at its transport, so the code under them runs as written, and the mailer faked at the router: resend's one answer for every outcome, asserted from the mailer side, including a license that is only suspended, and its 503 when mail is off before any lookup; each trial outcome, never with the file in the body, and a tagged address refused once the folded one holds a trial; `license_trial_issued` with only the channel, a bad channel dropped, and no event for a trial not issued; the success page's file and its 404; both rate-limit buckets biting, and a limit of zero turning one off. `test_keygen_contract.py` runs the client against a real Keygen when `KEYGEN_INTEGRATION=1`, proving the metadata keys the app writes are the ones it filters on, and that a key with another word answers an empty list. `test_stripe_webhook.py` posts events signed as Stripe signs them: a license purchase creates its license in Keygen, and an event signed with another secret is refused. The Business and subscription tests post signed events too, with Keygen and Stripe both faked at their transports (`tests/billing_harness.py`, `tests/stripe_fake.py`, the real `StripeClient` over a fake HTTP client) and the mail built for real and caught at the mailer. `test_business_purchase.py` covers a Payment Link's Business checkout: one license on the business policy with the people, firm, jobs and subscription, its first period plus 30 days, a validation before the `ttl: null` check-out, the Business mail, and the success page before the webhook. `test_subscription_lifecycle.py` covers a renewal on the same key and its mail, a retried one changing nothing, the first invoice before the checkout, people confirmed at renewal, a suspended license extended but not mailed, an Individual subscription sold before `stripeSubscriptionId` renewing on its own key, a seat change moving only `maxUsers`, a period advanced before payment extending nothing, and an ended subscription left to lapse. `test_money_returned.py` covers a refunded or disputed year suspending its subscription's license and no other, a proration or partial refund suspending nothing, a one-time payment with no Stripe customer traced, and an older Individual subscription traced through its checkout. `test_refresh_route.py` covers the refresh's file, its validation first, a suspended license refused, a lapsed one served, an unknown key, the key kept out of bucket names, both buckets and Keygen down. `test_business_trial.py` covers the trial switch off and on, an earlier trial not using up the Business one, and the switch without its policy. `test_setup_business_policies.py` covers the setup script against a faked Keygen account: both policies non-strict and joined to the live product, a second run creating nothing, a new job attached, the live policies only read, the refusals, and the product token only when asked. `test_license_routes.py` also covers a refunded purchase's success page and every check-out following its license's validation. `test_token_bucket.py` checks on a real Redis, CI's or a local `redis-server`, that two copies of the backend draw on one bucket; without one it skips. [`server/tests/`](../../../backend/server/tests/) check that the routes are served only with `KEYGEN_API_TOKEN`, that CORS answers the site, and that no `/docs` or `/openapi.json` is published.

## Known gaps

- The cohort report has not run against production Keygen or Stripe.
- The Keygen contract test has not yet run against a live Keygen; it skips without `KEYGEN_INTEGRATION=1` and credentials. Its cases for validation, a suspended license's check-out and an expiry moved on the same key have not run either, and neither has the setup script against Keygen CE.
- The app does not call `POST /license/refresh` yet, so a renewal reaches an Individual or Business user only by the renewal mail until it does.
- A dispute won later leaves its license suspended until support reinstates it.
- A job added to `jobs.py` reaches new licenses and the policies' entitlements, but the `jobs` already written on existing licenses keep the old list.
- The Business trial's two hidden rules in ADR 0080, Gmail dots folded into one address and at most two trials a year per company domain, are not built.
- Nothing checks the Payment Links' settings. Their after-payment redirect, the Business price's quantity limits and its `firm` field are set by hand in Stripe, and PostHog's 15 checkout clicks against 1 success page view in the 30 days to 21 Oct 2026 suggest the Individual link's redirect is not set.
