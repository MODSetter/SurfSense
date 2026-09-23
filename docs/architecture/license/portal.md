# License portal

The hosted backend sells, delivers and re-delivers the desktop app's license file with no accounts and no license table. Stripe and Keygen are the system of record: every search is a filter over Keygen license metadata, and the one direct read is by a derived id, and the license routes take no session, read no user table and touch no Postgres. Control of an inbox replaces the login, because a license is only ever mailed to the address it is registered to. Where having no table would cost a guarantee, the code moves the guarantee into Keygen instead of adding a table.

**Code:** [`surfsense_backend/app/license/`](../../../surfsense_backend/app/license/), [`surfsense_backend/app/mailer/`](../../../surfsense_backend/app/mailer/), [`surfsense_backend/app/payments/webhook.py`](../../../surfsense_backend/app/payments/webhook.py), [`surfsense_web/app/(home)/license/`](../../../surfsense_web/app/\(home\)/license/)
**Decisions:** [ADR 0024](../../adr/0024-portal-without-accounts.md), [ADR 0019](../../adr/0019-offline-licenses.md)

What the routes produce is [contract 1](../../contracts/01-license-file.md); the [desktop app](app.md) consumes it.

## Routes

All under `/api/v1`, unauthenticated, mounted from `app/routes/__init__.py`:

| Route | Answers |
|---|---|
| `GET /license/file?session_id=` | the `.lic` for that checkout session, or 404 |
| `POST /license/resend` `{email}` | 200 with the same body whatever it found |
| `POST /license/trial` `{email}` | 200 once the trial is mailed |
| `POST /stripe/webhook` | fulfilment and refunds, beside the credit handlers |

Both POSTs validate `email` as an email address and answer 422 for anything else.

### `GET /license/file`

The success page's download. It lists Keygen licenses whose `metadata[checkoutSessionId]` is `session_id` and checks out a fresh file. On a miss, when Stripe is configured, it retrieves the session and runs the same fulfilment as the webhook, because the buyer lands on the success page seconds after paying and `checkout.session.completed` can arrive later. A session that is missing or is not a license purchase is 404, and a Keygen failure is 500. `session_id` is required, since there is no signed-in user to fall back to. The answer is `text/plain` with `Content-Disposition: attachment; filename="surfsense.lic"`. The route needs no mail, which is why the success page, not the email, is the reliable delivery path.

### `POST /license/resend`

1. `503` when `SMTP_ENABLED` is false, before anything else.
2. The rate limits below; `429` when either bucket is empty.
3. List licenses by `metadata[email]`, skip `SUSPENDED` and `BANNED` ones, check out a fresh file for each and mail them all in one message.
4. `200` with "If a license is registered to that address, it is on its way.", whether it found three licenses or none, and also when the recipient's server refused the address.

After the success page this is the only way to get a license back, so an answer that varied with the outcome would make it an oracle for who is a customer. Skipping suspended licenses keeps it consistent with refunds. A transient mail failure or a Keygen failure answers 503.

### `POST /license/trial`

1. `404` when `LICENSE_TRIAL_ENABLED` is off; `503` when mail is off.
2. The rate limits, then `400` for a disposable domain: a built-in list, extended by `LICENSE_DISPOSABLE_EMAIL_DOMAINS`.
3. `409` when a license on the trial policy already carries this address's folded form in `metadata[trialKey]`.
4. Create the trial under a derived id with an explicit expiry, check it out and mail it: `200`.

The file is never in the response. Delivery to a real inbox is what makes one trial per email mean anything; handing the file back over HTTP would make unlimited trials a loop over throwaway strings. Unlike resend, trial has to say "already claimed", so it reports each outcome, including the ones after the create: a Keygen failure answers 503 and points at resend, which finds a trial that was created but not mailed; a transient mail failure answers 503 saying the trial exists; a refused recipient answers 400.

The expiry is `max(now, LICENSE_TRIAL_EXPIRY_FLOOR) + LICENSE_TRIAL_DAYS`, 30 days by default. The floor is for trials issued before the first plugin ships, so the wait does not eat the trial. Unset, the rule is plain "days from now"; an unparseable floor is ignored with a warning.

### Stripe webhook

`app/payments/webhook.py` verifies the signature and hands each paid checkout session to the handler that claims it (`app/payments/registry.py`); `app/license/purchase.py` registers the license's claims.

- `checkout.session.completed` with `payment_status` `paid` or `no_payment_required`, and `checkout.session.async_payment_succeeded`: the license handler claims a session whose metadata says `purchase_type: license`, or, with no `purchase_type` and a license price configured, whose line item is a license price. It fulfils the session, then emails the file. A mail failure does not fail the webhook: the license exists, the success page serves it, and a Stripe retry would only risk a duplicate.
- `charge.refunded`: lists licenses by `metadata[stripeCustomerId]` and suspends every one. Suspend, not revoke: it is reversible, the record stays listable for support, and Keygen's `validate-key` then reports `SUSPENDED`, which contract 2 maps to `revoked`.

Fulfilment also writes the license's Keygen id onto the Stripe customer as `keygen_license_id`, best effort, so a Stripe error cannot fail the webhook. Nothing reads it back; refunds find licenses through Keygen metadata.

### Plan resolution

`resolve_license_plan()` reads the plan two ways, so a Payment Link and an API-created session both work. Session metadata with `purchase_type: license` comes first (`plan` of `individual` or `team`, and `quantity` for team); otherwise the line item's price ID is matched against `STRIPE_PRICE_LICENSE_INDIVIDUAL` and `STRIPE_PRICE_LICENSE_TEAM`, with the line item quantity as the team's `maxUsers`. Webhook payloads carry no line items, so a Payment Link purchase costs one extra Stripe call. The site sells Individual through a Payment Link and no longer sells Team; the backend still supports it, and `scripts/issue_enterprise_license.py` issues team licenses by hand.

## Keygen as the database

| Metadata key | Set on | Used by |
|---|---|---|
| `plan` | every license | the app (contract 1) |
| `email` | every license | delivery, resend, shown in Settings |
| `trialKey` | trials | the one-trial-per-person check |
| `stripeCustomerId` | Stripe purchases | refund → suspend |
| `checkoutSessionId` | Stripe purchases | the success page, support corrections |

Keygen camelCases metadata keys in filter queries, and a misspelled filter returns an empty list rather than an error, which reads as "no license". The spellings live in `app/license/models.py`, except that `create_license()` in `keygen.py` writes `plan` and `email` as literals.

Certificates are never stored. Every delivery, whether success page, purchase mail or resend, checks out a fresh file with `{"meta": {"ttl": null}}`, so two files for one license differ in `meta.issued` and share a key. `ttl: null` matters because the app never refreshes, and Keygen's default 30-day TTL would kill every file a month after purchase.

## Idempotency without a table

The Keygen license id is derived, not assigned: `uuid5` of a fixed namespace and `stripe:<checkout session id>` for a purchase, or `trial:<folded email>` for a trial. When the webhook and the success page fulfil one payment at the same moment, both create the same id and Keygen refuses the second, with `422 ID_CONFLICT` when the first is already committed or a bare `409` when both are in flight, which the client confirms by fetching the id. For a purchase the loser reads the winner's license and delivers that; for a trial it answers 409. There is no lock and no table, and a second fulfilment cannot mint a second license; this replaces the earlier design of a Keygen lookup under a short Redis lock.

Only the id is derived. The license key stays Keygen-generated, because it is the bearer credential contract 2 sends to the scraper API and must be unguessable. The namespace is a constant rather than configuration, because changing it changes every derived id.

A trial has two guards. The derived id is the constraint that settles simultaneous claims; `trialKey` is a mutable index, so correcting an address can move it, which an id fixed at creation cannot follow.

## Email addresses

Delivery uses the address as typed, trimmed and lowercased. Deduplication, meaning the trial check and the per-email rate limit, also strips a `+tag` from the local part. `user+surfsense@gmail.com` is a real address the buyer may want the file at, so delivery must not fold it, but plus-tagging is the cheapest trial farm, so the trial check must. Dots are not folded: that is Gmail's rule, and applying it everywhere would collide distinct addresses at other providers. A trial stores both forms, `email` as typed and `trialKey` folded.

## Rate limits

Each POST takes a token from two buckets through the gateway's Redis token bucket (`app/gateway/ratelimit.py`), which falls back to per-process memory when Redis is down rather than failing closed:

| Bucket | Default per hour |
|---|---|
| `license:<route>:ip:<ip>` | 10 (`LICENSE_RATE_LIMIT_IP_PER_HOUR`) |
| `license:<route>:email:<folded>` | 5 for resend, 3 for trial (`LICENSE_RESEND_RATE_LIMIT_PER_HOUR`, `LICENSE_TRIAL_RATE_LIMIT_PER_HOUR`) |

The client IP comes from `get_real_client_ip()`, which prefers `CF-Connecting-IP`, then `X-Real-IP`, then the first `X-Forwarded-For` entry. The limits also bound mail spend and check-out load, since one resend is one check-out per license. A limit of zero turns its bucket off.

## Mail

`app/mailer/` is a port with one transport: `protocol.py` holds the `Mailer` protocol, the frozen `OutboundEmail` and `Attachment` payloads and the two errors; `factory.py` builds the mailer; `smtp.py` sends. The connection is deployment-wide (`SMTP_*`), not license-specific, and each feature stamps its own sender on its messages. SMTP is the transport because every transactional provider speaks it, Resend, Postmark, SendGrid, Mailgun, SES and Brevo among them, so choosing a vendor is filling in host, port, username, password and a From address. The sender is stdlib (`email.message` and `smtplib` through `asyncio.to_thread`), one connection per send, and adds no dependency.

- `SMTP_ENABLED` defaults to false, and there is no pretend-to-send mode. Both POST routes check it first and answer 503, because a resend that always answers 200 over a mailer that silently drops mail would make a broken deployment look like a working one.
- `SMTP_SECURITY` is explicit, `starttls` by default, `tls` or `none`, never guessed from the port. `none` is refused when a username is set, so credentials never cross in the clear; without one it only logs a warning for a non-loopback host.
- Every send failure maps to one of two errors; a configuration error is neither, since the mailer is built at the first send and a bad setting raises `ValueError` there (Known gaps). `MailerUnavailableError` covers connect failures, timeouts, 4xx replies, authentication failures and a refused sender, all ours to fix. `MailerRejectedError` is a permanent 5xx refusal during the conversation, of the recipient or of the message. A hard bounce arrives after a 250 accept, so trial promises "sent", never "delivered".
- `OutboundEmail.idempotency_key` is carried and ignored by SMTP, so a future API transport can dedupe retries without changing any caller.

`app/license/email/message.py` builds the three license messages, `purchase`, `resend` and `trial`, sent from `SMTP_LICENSE_FROM` or else `SMTP_FROM`, with `SMTP_LICENSE_REPLY_TO`. The file travels as `surfsense.lic`, numbered when one resend carries several, typed `application/octet-stream` so no mail client renders it inline and mangles its line endings. The install steps link the installers of the release pinned in `app/license/release.py`, looked up through the GitHub API and cached for an hour, or the release page when that lookup fails; pinning by tag keeps a mail already sent naming the build it was sent for ([updates](../updates.md)).

## Keygen

Production runs a self-hosted Keygen CE. Keygen Cloud bills per active licensed user and counts a check-out as activity, and here every delivery, trials included, is a check-out. `app/license/keygen.py` talks to `KEYGEN_API_URL`, or to Keygen Cloud when that is unset; when `KEYGEN_HOST` is set it sends that name as `Host` and adds `X-Forwarded-Proto: https`. `KEYGEN_ACCOUNT_ID`, `KEYGEN_API_TOKEN` and the three `KEYGEN_POLICY_*` variables mean the same on either. CE is not a service in `docker/docker-compose.yml`; its web and worker images are in [`docker/keygen/`](../../../docker/keygen/).

Three things break a CE instance's first boot or first call:

1. Setup needs four secrets, `SECRET_KEY_BASE`, `ENCRYPTION_DETERMINISTIC_KEY`, `ENCRYPTION_PRIMARY_KEY` and `ENCRYPTION_KEY_DERIVATION_SALT`. Given those plus `KEYGEN_ACCOUNT_ID`, `KEYGEN_ADMIN_EMAIL`, `KEYGEN_ADMIN_PASSWORD`, `KEYGEN_EDITION=CE` and `KEYGEN_MODE=singleplayer`, `setup` runs non-interactively.
2. `KEYGEN_HOST` must be a dotted name with a parseable eTLD+1. A single label, `localhost` or a bare compose service name, crashes boot in `resolve_account_service.rb`; use a name like `keygen.internal`, or set `KEYGEN_DOMAIN` and `KEYGEN_SUBDOMAIN`.
3. Keygen forces TLS and answers plain HTTP with a 308 to `https://`. It does not terminate TLS, but it trusts `X-Forwarded-Proto: https` from RFC 1918 peers, so an internal caller needs that header rather than a TLS terminator. Without it every call redirects and reads as an empty result.

The account's public key is not exposed over the API; read it with `rails runner "puts Account.sole.ed25519_public_key"`. That keypair is the most critical secret in the system. The desktop app accepts only files signed by a key compiled into it, and that key is meant to be this account's, so losing the private half means no shipped binary accepts a new file until a release trusts a new key. Back it up out of band, separate from the Postgres dump.

## Files

Under `surfsense_backend/app/license/`:

| File | Responsibility |
|---|---|
| `router.py` | the three license routes |
| `keygen.py` | the Keygen client: create, get, check out, list by metadata, update metadata, suspend |
| `issue.py` | minting: derived ids, trial expiry, fulfilling a purchase, the file for a session |
| `checkout.py` | reading a Stripe session: email, customer, plan |
| `purchase.py` | the webhook claims: fulfil and mail, suspend on refund |
| `records.py` | reading licenses back by session, email or id |
| `admin.py` | refunds and address corrections |
| `models.py` | metadata key spellings, errors and value types |
| `schemas.py` | the request and acknowledgement bodies |
| `rate_limit.py` | the two buckets |
| `release.py` | the desktop release the mail links to |
| `email/address.py` | normalizing, folding, the disposable-domain list |
| `email/deliver.py` | handing a built message to the mailer |
| `email/message.py` | subjects, bodies, attachments and sender |

Two support scripts sit in `surfsense_backend/scripts/`. `issue_enterprise_license.py` issues an invoiced license without Stripe and prints the file, and also mails it with `--mail`. `correct_license_email.py` repairs a mistyped purchase address, below.

## Pages

In `surfsense_web`, all public routes:

- `/license/success` is where Stripe returns the buyer. It downloads the file once on mount, since that first request may be what creates the license, then leaves retries to a button rather than looping. A 404 reads as "payment is still settling, press again", never "you have no license".
- `/license` has only the resend form. Resend can never say "no license found", so its success copy tells the user to check spam and use the exact address they paid with.
- The trial form is on `/downloads`, beside the installers a license file is useless without.
- `/license/activate` is the activation guide the mail links to.

The pages state two dead ends plainly. An enterprise license is one file sent only to the buying address, so a colleague asks the buyer to forward it. A lost or mistyped inbox has no self-serve path, because a form that mailed a license to a newly typed address would be a way to steal one.

## Support corrections

A buyer who mistyped the checkout email and also closed the success page before saving the file reaches support. Support asks for proof only the payer holds, the charge id from the bank statement or the last four digits, amount and date, finds the charge in Stripe and runs:

```bash
python -m scripts.correct_license_email --session cs_... --email real@buyer.com --mail
```

The script matches on the payment, never on how alike two addresses look: `checkoutSessionId` names exactly one license, and the script refuses when two carry it. It prints the record, asks for confirmation unless `--yes` is passed, rewrites the stored `email`, and then mails a fresh file with `--mail` or prints it. Rewriting the address is the point, because resend looks customers up by it; a typo left in Keygen makes every future download another ticket. A buyer who lost the inbox takes the same path. Someone who fools support gets one license that can be suspended, a risk accepted over identity checks.

## Tests

`tests/unit/license/test_issue.py` covers Keygen payload shapes, metadata filter syntax, the CE headers, trial expiry, address folding, plan resolution, derived ids and both duplicate-id answers; `test_message.py` and `test_release.py` cover the mail and the release lookup. `tests/unit/mailer/` covers the SMTP error mapping, MIME shape, senders and configuration checks, and `tests/integration/mailer/test_smtp_contract.py` sends through a real SMTP conversation against Mailpit when `SMTP_INTEGRATION=1`. The route and rate-limit suites, and the Keygen and mailer fakes they stood on, were deleted on 15 Sep 2026 in commit `7f1195c76`.

## Known gaps

- A refund suspends every license the Stripe customer holds, partial refunds included.
- A bad SMTP configuration raises on the first send, not at startup, so `/license/trial` can create the trial and then fail with 500.
- No test covers the license routes or their rate limits, and no contract test runs the Keygen client against a real Keygen.
- `correct_license_email.py` finds a license only by `--session`, so a trial's address cannot be corrected through it.
