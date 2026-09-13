# Portal — Phase 1: license routes

> Owns: the four unauthenticated license endpoints in `surfsense_backend`, the
> Keygen producer client, and the transactional mail port.
> Workstream B. Contract it produces: [`../contracts/01-license-file.md`](../contracts/01-license-file.md).

## The two product decisions this doc implements

1. **No login on the portal, no license table.** Stripe and Keygen are the
   system of record. The license is tied to the buyer email in Keygen
   `metadata`. Re-download is a resend: email in, Keygen lookup by metadata
   email, file mailed back. Trial is the same shape. Nothing here reads or
   writes the user table, and no route takes a session.
2. **No separate database.** Postgres stays up for the scraper API's own
   operational rows only; user data is purged at T+30. The license path
   touches Postgres not at all.

Everything below follows from those two sentences. Where a weaker guarantee is
the price of having no table, this doc says so rather than hiding it.

## Endpoints

All four are unauthenticated. None takes an `AsyncSession`.

| Method | Path | Body / query | Success |
|---|---|---|---|
| `GET` | `/license/file` | `session_id` (**required**) | `200` the `.lic` bytes |
| `POST` | `/license/resend` | `{"email": "..."}` | `200` acknowledgement, always |
| `POST` | `/license/trial` | `{"email": "..."}` | `200` acknowledgement |
| `POST` | `/stripe/webhook` | Stripe event | existing route, two new branches |

### `GET /license/file?session_id=`

Serves the success page. Resolution is Keygen-only:

1. List licenses filtered by `metadata[checkoutSessionId] == session_id`.
2. Hit → check out a fresh certificate (`ttl: null`) and return it.
3. Miss → retrieve the session from Stripe and run the same fulfilment the
   webhook runs, then return the certificate. This is the webhook-vs-redirect
   race: the buyer lands on the success page seconds after paying, and
   `checkout.session.completed` can take 5-30s.
4. Still nothing → `404`.

`session_id` is required. The old build fell back to "the signed-in user's
latest license", which is the login coupling the product decision removes;
there is no fallback to replace it.

Response is `text/plain` with
`Content-Disposition: attachment; filename="surfsense.lic"`.

### `POST /license/resend`

1. Rate-limit on IP and on the normalized email (below).
2. Require a configured mailer, else `503`. See **Delivery**.
3. List Keygen licenses by `metadata[email]`.
4. Check out each one and mail them all to that address.
5. Return `200` regardless of how many were found — **including zero**.

The response body must not vary by outcome. This endpoint is the only way to
retrieve a license after the success page, so it would otherwise be an email
oracle: type an address, learn whether that person is a customer.

Because the address is where the file goes, it is also the authorization
check. Proving control of the inbox is what replaced the login.

### `POST /license/trial`

1. Rate-limit as above.
2. Require a configured mailer, else `503`.
3. Reject disposable domains (`400`).
4. Under a lock on the normalized email, list the **trial policy** filtered by
   `metadata[email]`. Non-empty → `409`.
5. Create the trial license, check out, mail it.

Unlike resend, trial cannot hide its outcome — it has to say "already
claimed". Abuse pressure is carried by the rate limiter and the blocklist
instead.

The trial file is **not** returned in the HTTP response. Requiring delivery to
a real inbox is what makes one-trial-per-email mean anything; handing the file
back over HTTP would make unlimited trials a loop over throwaway strings.

### Stripe webhook branches

`checkout.session.completed` where the session is a license purchase
(see **Plan resolution**) runs fulfilment. `charge.refunded` resolves the
customer, reads `keygen_license_id` from the Stripe customer metadata, and
**suspends** the license in Keygen.

Suspend, not revoke: it is reversible, it keeps the record listable for
support, and Keygen's `validate-key` returns `SUSPENDED`, which maps onto
contract 2's `revoked` reason. A revoked license is deleted and a refund
reversal would have nothing to restore.

## Keygen as the database

Every license carries this metadata, and every lookup is a filter over it:

| Key | Set on | Used by |
|---|---|---|
| `plan` | all | the app (contract 1) |
| `email` | all | delivery, resend lookup, shown in Settings |
| `trialKey` | trials | the one-trial-per-person check |
| `stripeCustomerId` | Stripe purchases | refund → suspend |
| `checkoutSessionId` | Stripe purchases | success page, idempotency |

**Keygen camelCases metadata keys in filter queries.** A snake_case filter key
returns an empty list rather than an error, which here means "no license
exists" — which means a duplicate gets issued. The integration contract test
covers exactly this.

Certificates are never stored. Every delivery checks out a fresh one, which is
why the same license yields files with different `meta.issued` — a contract-1
consequence, recorded there.

## Idempotency and dedupe without a table

The old build used a unique row on `stripe_checkout_session_id` plus
`pg_advisory_xact_lock`. Both are gone. Replacements:

**Purchase.** The Keygen list by `metadata[checkoutSessionId]` is the durable
check; Keygen is the record, so it is authoritative. A short Redis lock on the
session id narrows the read-then-create window between the webhook and the
success page.

**Trial.** The Keygen list on the trial policy by `metadata[email]`, under a
Redis lock on that email.

**Accepted weakness, stated deliberately:** a list-then-create is not an atomic
unique constraint. A pathological race inside the lock TTL can mint two
licenses for one payment. It is bounded by the lock, visible in the Keygen
dashboard, and the buyer gets a working file either way. We take that over
reintroducing a table. Duplicate trials are bounded by the same window and by
the rate limiter.

Redis is already kept alive through the tail for the gateway limiter and the
Google Search IP pool, so this adds no infrastructure.

## Email normalization

Delivery uses the address as typed (lowercased, trimmed). Dedupe uses a
folded form: lowercase, trim, and strip `+tag` from the local part.

The split matters. `user+surfsense@gmail.com` is a real deliverable address and
the buyer may want the file there, so folding it for delivery would send mail
to the wrong place. But plus-tagging is the cheapest possible trial farm, so
the trial check folds it. Dots are **not** folded: that is Gmail-specific
behaviour, and applying it to every provider would wrongly collide distinct
addresses elsewhere.

Because both forms are needed, a trial license stores **both**: `email` is the
address as typed (delivery, resend, what Settings shows) and `trialKey` is the
folded form the dedupe query filters on. Storing only the folded form would
misdirect delivery; storing only the typed form would let a tagged address
claim a trial that the fold could never find again, which defeats the check for
exactly the addresses it exists to catch.

## Rate limits

Two token buckets per request, both through the existing Redis limiter in
`app/gateway/ratelimit.py` (which already falls back to per-process memory
during a Redis outage rather than failing closed):

| Scope | Default |
|---|---|
| `license:<route>:ip:<ip>` | 10/hour |
| `license:<route>:email:<folded>` | 5/hour resend, 3/hour trial |

Over budget → `429`. Client IP comes from `get_real_client_ip`, which already
handles the Cloudflare and reverse-proxy headers this deployment sits behind.

These also protect the Keygen tier quota: one resend is N check-out calls.

## Delivery: a port, no provider decision

There is no transactional email anywhere in this codebase today — the
fastapi-users hooks print tokens to stdout and the web contact form writes a
row and notifies nobody. Rather than commit to a vendor, this ships an adapter
and defers the choice.

`app/mailer/` mirrors the `app/sandbox/` idiom already used here: a `Protocol`
plus frozen payload dataclasses, a config-selected factory with lazy imports,
and transports behind it.

One naming rule, because it is the thing readers trip on:
`LICENSE_MAIL_TRANSPORT` selects **how** mail leaves the process — discard,
log, or SMTP — and never **who** delivers it. No vendor name appears in any
executable line of the backend. Changing company means editing the SMTP
connection strings; the transport stays `smtp` forever.

**The transport is SMTP**, because SMTP is the actual universal interface:
Resend, Postmark, SendGrid, Mailgun, SES and Brevo all expose it, and all of
them reduce to host/port/username/password. Choosing a vendor later is filling
in five strings, not writing code.

| Provider | Host | Port | Username | Password |
|---|---|---|---|---|
| Resend | `smtp.resend.com` | 587 | `resend` | API key |
| Postmark | `smtp.postmarkapp.com` | 587 | Server API token | same token |
| SendGrid | `smtp.sendgrid.net` | 587 | `apikey` | API key |
| Mailgun | `smtp.mailgun.org` | 587 | `postmaster@<domain>` | SMTP password |
| Amazon SES | `email-smtp.<region>.amazonaws.com` | 587 | SMTP username | SMTP password |
| Brevo | `smtp-relay.brevo.com` | 587 | account email | SMTP key |

Confirm at signup; these move occasionally. **SES SMTP credentials are not IAM
access keys** — they are derived from an IAM secret in the SES console.

Implementation is stdlib: `email.message.EmailMessage` builds the MIME tree,
`smtplib` sends it, `asyncio.to_thread` keeps the route async. **No new
dependency.** One connection per send; pooled SMTP connections go stale and the
reconnect logic would cost more than it saves at this volume.

`aiosmtplib` was the alternative — native async, one small dep. Rejected only
because zero dependencies was worth more than the threadpool hop here.

### Transports

| `LICENSE_MAIL_TRANSPORT` | Behaviour |
|---|---|
| `null` | discards; the default, and what unit tests use |
| `console` | logs the envelope and writes the `.lic` to a temp path; local dev |
| `smtp` | the real one |

Transport selection is a deployment choice, **not a fallback chain**. An
unreachable SMTP server is an error to fix, never a reason to silently drop
mail — the same rule `app/sandbox/factory.py` states for sandboxes.

It is also deliberately **explicit rather than inferred** from whether an SMTP
host is set. Inference makes a typo silent: misspell the host variable and the
deployment quietly resolves to "discard", which is exactly the trap the next
section describes. Declaring the transport means a mismatch — `smtp` with no
host — fails at startup instead of at 2am.

### The null-transport trap

`/license/resend` always returns `200` so it cannot be used to probe emails. A
no-op mailer also returns success. Together those make a misconfigured
deployment **indistinguishable from a working one**: the customer asks for
their license, gets a cheerful `200`, and nothing ever arrives.

So both POST routes return `503` unless the transport actually delivers,
checked *before* any Keygen lookup — which leaks nothing, because it is
outcome-independent. `GET /license/file` is unaffected and works with no
mailer at all, which is why the success page remains the reliable delivery
path.

### Error taxonomy

No provider exception escapes `app/mailer/`. Two errors reach callers:

| Condition | Error |
|---|---|
| connect failure, disconnect, timeout, DNS | `MailerUnavailableError` |
| SMTP auth failure | `MailerUnavailableError` — our misconfiguration, never the user's address |
| 4xx (greylisting, rate limit, temp full) | `MailerUnavailableError` |
| 5xx recipient refused (550/551/553) | `MailerRejectedError` |
| sender refused | `MailerUnavailableError` — unverified From domain is our problem |

The 4xx/5xx split is protocol-level and identical at every provider, which is
what makes one mapping serve them all.

A hard bounce arrives *after* a 250 accept, so `MailerRejectedError` only
catches in-conversation refusals. A typo'd address that accepts-then-bounces
looks like success. The trial route therefore promises "sent", never
"delivered", and the success page is the guarantee for purchases.

### Templates

Subject lines and bodies live in `app/mailer/templates.py`, on our side of the
port — never in a provider and never hosted at a vendor. This is what keeps a
provider swap from becoming a copy migration. Three kinds: `purchase`,
`resend`, `trial`.

### Idempotency key

`LicenseEmail.idempotency_key` is carried by the port and ignored by SMTP,
which has no equivalent. It exists so a future API-based transport can dedupe
retries without changing call sites. A duplicate license email is a nuisance,
not a correctness bug.

## Trial expiry

[00d](../00d-pivot-plan.md) requires trials issued before the plugin ships to
expire at T+7 plus 14 days, so the gap week does not eat the trial. The Keygen
policy's own duration cannot express that, so `create_license` takes an
explicit `expiry`: `max(now, LICENSE_TRIAL_EXPIRY_FLOOR) + LICENSE_TRIAL_DAYS`.
With the floor unset the rule degrades to plain "14 days from now", which is
the correct behaviour once the plugin has shipped.

## Plan resolution

The pricing page sends buyers straight to Stripe Checkout. That can be a
**Payment Link** (no backend code, no login) or an API-created session. Payment
Links set no session metadata, so the webhook resolves the plan in two steps:

1. `metadata.plan` / `metadata.quantity` when present (API-created sessions).
2. Otherwise the line item's price ID, matched against
   `STRIPE_PRICE_LICENSE_INDIVIDUAL` / `STRIPE_PRICE_LICENSE_TEAM`, with the
   line item quantity as `maxUsers` for team.

Supporting both costs a few lines and means the Payment-Link-vs-API decision
never blocks this code again.

## Configuration

```
KEYGEN_ACCOUNT_ID=
KEYGEN_API_TOKEN=
KEYGEN_POLICY_TRIAL=
KEYGEN_POLICY_INDIVIDUAL=
KEYGEN_POLICY_TEAM=

LICENSE_TRIAL_ENABLED=FALSE
LICENSE_TRIAL_DAYS=14
LICENSE_TRIAL_EXPIRY_FLOOR=          # ISO date; unset once the plugin ships
LICENSE_DISPOSABLE_EMAIL_DOMAINS=    # extends the built-in list

LICENSE_MAIL_TRANSPORT=null          # null | console | smtp (how, not who)
LICENSE_MAIL_FROM=
LICENSE_MAIL_REPLY_TO=
LICENSE_MAIL_SMTP_HOST=
LICENSE_MAIL_SMTP_PORT=587
LICENSE_MAIL_SMTP_USERNAME=
LICENSE_MAIL_SMTP_PASSWORD=
LICENSE_MAIL_SMTP_SECURITY=starttls  # starttls | tls | none
LICENSE_MAIL_TIMEOUT_SECONDS=20

LICENSE_RATE_LIMIT_IP_PER_HOUR=10
LICENSE_RESEND_RATE_LIMIT_PER_HOUR=5
LICENSE_TRIAL_RATE_LIMIT_PER_HOUR=3

STRIPE_PRICE_LICENSE_INDIVIDUAL=
STRIPE_PRICE_LICENSE_TEAM=
```

`LICENSE_MAIL_SMTP_SECURITY` is explicit rather than inferred from the port.
465 is implicit TLS and 587 is STARTTLS; guessing from the port number is the
classic source of "it hangs forever with no error". `none` is refused unless
the host is loopback, so a production typo cannot send credentials in clear.

## Files

```
app/mailer/
  protocol.py     Mailer, LicenseEmail, Attachment, the two errors
  factory.py      build_mailer() / is_mail_enabled(); lazy imports
  templates.py    subjects and bodies for the three kinds
  transports/     null.py, console.py, smtp.py
surfsense_web/app/(home)/license/
  page.tsx + license-forms.tsx          resend and trial forms, no login
  success/page.tsx + license-download.tsx  serves the file by checkout session
app/services/
  keygen.py             + list_licenses, update_license_metadata,
                          suspend_license, expiry, extra metadata
  license_service.py    table-free; returns IssuedLicense, takes no session
  license_locks.py      Redis lock replacing pg_advisory_xact_lock
  license_rate_limit.py two buckets over the gateway limiter
  license_email.py      normalization + disposable-domain blocklist
app/routes/license_routes.py    three routes, no auth, no session
app/schemas/license.py          LicenseEmailRequest, LicenseAckResponse
scripts/correct_license_email.py  the support correction above
```

## Tests

| Layer | Covers |
|---|---|
| `tests/unit/mailer/` | SMTP error mapping, MIME shape, transport selection, plaintext refused with credentials, templates |
| `tests/unit/services/test_license_issue.py` | Keygen payload shapes, plan resolution, trial expiry floor, normalization/folding, support corrections |
| `tests/integration/test_license_routes.py` | route wiring, idempotency via Keygen list, resend 200-on-miss, trial dedupe, 503 with no mailer, 429, refund → suspend |
| `tests/utils/fake_keygen.py`, `fake_mailer.py` | recording fakes, mirroring `fake_sandbox.py` |

The fakes are what let all of this be tested with no Keygen account and no
mail provider. A live SMTP contract test, opt-in behind an env flag like
`tests/integration/sandbox/test_opensandbox_contract.py`, is the single test
that needs a real vendor, and it stays skipped until one exists.

## The `/license` and `/license/success` pages

B5 names these in one line each. They are specified here because every failure
mode they must render is a decision made above.

**`/license/success`** is the *reliable* delivery path, not the email. It
serves the file straight from the checkout session, so it still works when the
buyer mistyped their address. It downloads once on mount — the webhook can lag
the redirect by 30s, so that first attempt may be what creates the license —
then leaves retries to a button rather than looping. A 404 means "payment is
still settling, press again", never "you have no license".

**`/license`** carries two forms with deliberately asymmetric feedback:

| | Resend | Trial |
|---|---|---|
| `200` | *"If a license is registered to that address, it is on its way."* | "Your trial is on its way." |
| `409` | — | "A trial has already been claimed for that address." |
| `400` | — | "Use a permanent email address." |
| `404` | — | "Trials are not open yet." |
| `429` | "Too many requests from here." | same |
| `503` | "We cannot send email right now." | same |
| `422` | "That does not look like an email address." | same |

Resend can never say "no license found" — that would make it an oracle for who
is a customer. So its success copy must also do the work the error copy cannot:
*check spam, use the exact address you paid with*. Without that, a typo is
indistinguishable from success and the user has nothing to act on. Trial has no
such constraint: it has to say "already claimed", so there is nothing left to
hide.

The page also states the two dead ends plainly, because neither is a bug to be
fixed later:

- **Team licenses** are one file sent only to the buying address. A team member
  asks the buyer to forward it.
- **A lost or mistyped inbox** has no self-serve path *by design* — if you
  could name an address and have a license delivered elsewhere, resend would be
  a way to steal one. The page routes these to support with payment details.

## Support runbook

Two cases reach a human. Both are rare, and neither should become self-serve.

### A buyer mistyped their email at checkout

The success page serves the file regardless of the address, so this only
reaches someone who *also* closed the tab before saving. Expect very few.

1. Ask for proof of payment only they could hold: the charge id from their bank
   statement, or last 4 + amount + date.
2. Find that charge in Stripe; take its checkout session id.
3. `python -m scripts.correct_license_email --session cs_… --email real@buyer.com --mail`

The script matches on the **payment**, never on how similar two addresses look
— `checkoutSessionId` names exactly one license, so there is no judgement call
about whether "gmial" meant "gmail". It prints the record for the operator to
check, then rewrites the stored address.

**Rewriting the address is the point, not the resend.** Mail them the file and
leave the typo in Keygen and every future re-download is another ticket,
because resend looks the customer up by that stored address. Correcting it
turns them back into a self-serve customer permanently.

For a trial, the script moves `trialKey` along with `email`; leaving the old
fold behind would let the corrected address claim a second trial.

If two licenses carry one session id, the script refuses rather than guessing —
that means the idempotency race lost and a duplicate needs resolving in Keygen
first.

**Residual risk, accepted:** this is a social-engineering path. Someone who
fools support gets one license, which is suspendable server-side, on a $120/yr
product. Requiring Stripe-verifiable evidence is proportionate; identity
verification is not.

### A buyer lost access to that inbox entirely

Same verification, same script. There is no other route: resend *is* the inbox.

## Out of scope

The sunset flags (B4), the rest of the portal pages (B5), and the T+7 scraper
license mode,
which resolves `Authorization: License <key>` to a synthetic user and workspace
per license key with no account linking — see
[`../contracts/02-scraper-api-auth.md`](../contracts/02-scraper-api-auth.md).
