# Account Deletion and the One-Time Welcome Credit

**Status:** Planned, not started.
**Goal:** Ship self-serve account deletion, and stop the welcome credit from being re-issued when a deleted user registers again.

## 1. Problem

Three requirements, two of which pull against each other.

**Users must be able to delete their account.** Today they cannot: the privacy policy (section 7) says "you can request deletion at any time" but the only route is emailing `rohan@surfsense.com`. There is no `DELETE` on `/users/me`, and `user-settings/profile` edits display name only.

**Deleting must not become a way to farm credit.** Every account starts with $5 because `User.credit_micros_balance` carries a SQL default of `DEFAULT_CREDIT_MICROS_BALANCE` (5,000,000 micro-USD). There is no welcome-grant event and no identity check — any new row is a new $5. With a delete button in the product, "spend, delete, re-register" becomes an unbounded free-compute loop against real LLM spend.

Erasing the person and remembering that the person already claimed $5 are required at the same time.

## 2. Decisions

**Re-registration stays allowed.** A returning user gets a working account, just not a second welcome grant. No deny list.

**The grant is keyed to an identity, not to a user row.** A separate table records which identities have claimed, and it is never cascaded by user deletion.

**Google `sub` is the only identity source in v1.** Production runs `AUTH_TYPE=GOOGLE`, so `sub` covers every account that can cost money. It is stable per Google account and immune to email spelling, which removes per-provider email normalization from scope entirely.

**Self-hosted stays ungated.** `AUTH_TYPE=LOCAL` installs produce no identity key, so they keep granting the default balance. That is correct: the operator funds their own inference, and there is nothing to farm.

**Only a keyed hash is retained.** HMAC-SHA256 under the existing `SECRET_KEY`, never a raw provider id or email. Under ICO guidance this is pseudonymisation, not anonymisation, so it stays disclosed in the privacy policy as a legitimate-interest retention (fraud prevention, GDPR Recital 47).

**No grace period.** Deletion is immediate and irreversible. Lockout is synchronous; the heavy erase runs in Celery within seconds, matching how workspace deletion already works. A recovery window, if wanted later, is additive.

**Deleting an account deletes every workspace it owns, shared or not.** Members of a shared workspace lose it; the dialog says so before the user confirms. Nobody has asked to keep a shared workspace alive past its owner, so nothing is built for it.

### Rejected

| Option | Why not |
| --- | --- |
| Block re-registration by email | Punishes legitimate returners; the ask was to allow return without the grant. |
| Device fingerprint / IP clustering | Personal data under Recital 30, VPN false positives, new vendor. Solves multi-account farming, a different and unobserved problem. |
| Require a card for the $5 | Kills the "no credit card required" conversion the marketing pages sell. The right lever only once abuse is measured. |
| Email normalization (Gmail dots, `+tags`) | Not needed while Google is the only production login. Written the day password auth is enabled, as one new source function. |
| Plaintext email on a tombstone | More PII than the job needs. |
| Auto-promote the longest-tenured member | Silent. The successor inherits responsibility they never accepted. |
| Workspace ownership transfer, and blocking deletion until it happens | Two features (transfer endpoint, a per-workspace resolution step in the delete dialog) for a case nobody has reported. Deleting what you own is the behaviour every other resource here already has. Build it when a user asks. |

## 3. Identity claims ledger

### Table

`identity_claims`, created by migration `186`:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer PK | `BaseModel` convention |
| `kind` | text, not null | `google_sub` today; `email`, `github_id` later |
| `value_hmac` | text, not null | `HMAC-SHA256(SECRET_KEY, "<kind>:<value>")`, hex |
| `claimed_at` | timestamptz, not null | Backfilled from `user.created_at` |

Unique constraint on `(kind, value_hmac)`.

**No foreign key to `user`, and no `user_id` column.** This is the load-bearing property: user deletion must not cascade the row away. Folding `kind` into the hashed input keeps two identity spaces from colliding on the same underlying value.

Not added to `ZERO_PUBLICATION`. That module is an explicit allowlist and `verify_publication` flags unexpected tables, so a new table stays unreplicated with no change — which is what we want, since no frontend reads it.

### Registry

`app/services/identity_claims.py` holds an `@identity_source` registry. Each source takes a user and yields `(kind, value)` pairs; `claim_keys(user)` returns the union.

v1 registers one source, `_google_sub`, reading `user.oauth_accounts` for `oauth_name == "google"`.

**The `people/` prefix must be stripped.** Pre-`sub` Google rows stored `people/<sub>`. Migration `169` normalized them but deliberately skipped any row whose bare-sub twin already existed, and `resolve_google_user` in `auth_routes.py` still carries a runtime fallback with a TODO confirming production is not verified clean. Hashing `account_id` raw would give one human two different keys. The strip lives in `_google_sub`, and the backfill calls that same function so the two paths cannot drift.

Adding a login method later is one new decorated function. Because `claim_keys` returns the union and any single matching key blocks the grant, a user who claimed via Google and returns via a future password signup is caught by whichever key overlaps.

### Grant

`claim_welcome_credit(session, keys) -> int` returns the micro-USD to grant and records the claim in one statement:

```
INSERT INTO identity_claims (kind, value_hmac, ...) VALUES (...)
ON CONFLICT (kind, value_hmac) DO NOTHING
```

Grant iff `rowcount == len(keys)`. The insert *is* the check, which removes the read-then-write race between two concurrent registrations of the same identity. On the losing path the new keys still land, linking a returning user's newer identities to their original claim.

An empty key list grants the default and logs a warning. Every registration path should contribute at least one key; a path contributing none is ungated — it grants on every signup and records nothing to stop the next one. Correct for self-hosted LOCAL, a production incident for anything else, so it must be visible in logs rather than silent.

### Wiring

`User.credit_micros_balance` default and `server_default` drop to `0`. `UserManager.on_after_register` extracts keys from the passed user, then inside its existing session sets the balance from `claim_welcome_credit`.

Ordering is safe: fastapi-users `manager.py` calls `add_oauth_account` (line 218) before `on_after_register` (line 219), so the Google row exists when keys are extracted. The `associate_by_email` branch does not call `on_after_register` at all, so linking a second provider to an existing account correctly grants nothing.

### Backfill

Same migration, after table creation. Batched through Python rather than pure SQL, because the HMAC needs `SECRET_KEY` and must use the identical function the runtime uses. Reads `"user"` joined to `oauth_account` where `oauth_name = 'google'`, writing one claim per user with `claimed_at = user.created_at` — historical is more honest than migration time and gives a real audit timeline.

`ON CONFLICT DO NOTHING` absorbs the legacy-plus-canonical duplicate subs left by migration 169. First row wins; neither existing account loses credit it already holds. We stop future claims, we do not claw back.

LOCAL databases have no `oauth_account` rows, so the backfill writes nothing and existing self-hosted users are unaffected.

## 4. Account deletion

### Route

`DELETE /users/me` in `app/routes/users_routes.py`, behind `require_session_context` so a leaked PAT cannot destroy an account.

Synchronously: set `is_active = False` and revoke all refresh tokens via the existing `revoke_all_user_tokens`. That is the entire lockout — `get_auth_context` already gates both the session and PAT paths on `user.is_active`, so no new column and no auth changes are needed. Then enqueue the erase task, clear the session cookie, and return `204`.

Nothing about deletion touches `identity_claims`: the claim was written at grant time and simply survives.

### Erase task

`delete_user_task`, with the retry/backoff options used by `delete_workspace_task`. Steps, in order:

1. For each owned workspace, call the existing `_delete_workspace_background(workspace_id)` — batched chunk and document deletion, `purge_document_blobs`, then `drop_workspace_store`. Reusing this is the point: raw FK cascade from `user` would drop workspace rows while orphaning blobs and git trees.
2. Best-effort delete the Stripe customer when `stripe_customer_id` is set. Charges and invoices stay at Stripe under GDPR 17(3)(b); Stripe is the system of record for tax.
3. Delete the user row. Existing cascades handle memberships, notifications, prompts, PATs, refresh tokens, incentive tasks, OAuth accounts, and purchases.

Idempotent throughout, so a retry after a partial run completes rather than failing. If the task exhausts retries the account is locked out with data intact and the failure is visible in Celery — recoverable, unlike a half-cascade.

### Retained after deletion

The `identity_claims` row (welcome-grant control). Stripe-side charges and invoices (tax). Workspaces the user was only a member of. Nothing else.

## 5. Deletion UI

Danger zone at the bottom of `user-settings/profile`, using the existing shadcn dialog and the `userSettings` i18n namespace.

Confirmation requires typing `DELETE` and states: every workspace they own is destroyed along with its chats, documents, connectors, and API keys, and anyone they share one with loses that work; remaining credit is forfeited and not refunded; a new account with the same Google identity will not include the $5 welcome credit.

On success, clear client state and redirect to the marketing home.

## 6. Policy

Privacy policy section 7 gains: deletion is self-serve in Settings; deletion is immediate; we retain a one-way keyed hash of your account identifier solely to prevent re-issue of promotional credit (legitimate interest); Stripe retains invoices for tax.

## 7. Tests

- **Welcome credit:** same Google `sub` twice grants `$5` then `$0`; a user with no OAuth account still grants `$5` and logs the ungated warning; `people/<sub>` and bare `<sub>` resolve to one key.
- **Deletion:** deactivates and revokes tokens; rejects the PAT path; the erase task removes the user and every workspace they owned, shared ones included, leaves workspaces they were only a member of alone, and is safe to run twice.

## 8. Follow-ups

**`CreditPurchase` cascade.** Purchase rows are `cascade="all, delete-orphan"` and vanish with the user. Accepted: Stripe retains the authoritative charge record. Revisit if local invoice history is ever needed for accounting.

**Daytona sandboxes.** Labeled per thread, not per user, so deleting threads leaves sandboxes to provider TTL. Out of scope; add a best-effort kill if it shows up as cost.

**PostHog person deletion.** `distinct_id` is `str(user.id)`, so a person object survives. Needs a PostHog API call not currently wired.

**Retire the `people/` fallback.** Once the backfill confirms zero `oauth_account` rows matching `people/%`, the legacy branch in `resolve_google_user` and the strip in `_google_sub` can both go.
