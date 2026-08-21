# Account Deletion, Ownership Transfer, and the One-Time Welcome Credit

**Status:** Planned, not started.
**Goal:** Ship self-serve account deletion, make workspace ownership transferable so deletion never destroys other people's work, and stop the welcome credit from being re-issued when a deleted user registers again.

## 1. Problem

Three requirements, two of which pull against each other.

**Users must be able to delete their account.** Today they cannot: the privacy policy (section 7) says "you can request deletion at any time" but the only route is emailing `rohan@surfsense.com`. There is no `DELETE` on `/users/me`, and `user-settings/profile` edits display name only.

**Deleting must not become a way to farm credit.** Every account starts with $5 because `User.credit_micros_balance` carries a SQL default of `DEFAULT_CREDIT_MICROS_BALANCE` (5,000,000 micro-USD). There is no welcome-grant event and no identity check — any new row is a new $5. With a delete button in the product, "spend, delete, re-register" becomes an unbounded free-compute loop against real LLM spend.

**Deleting must not destroy other people's work.** Workspaces are multi-member. If the deleting user owns a shared workspace, erasing it takes every other member's documents and chats with it.

Erasing the person, remembering that the person already claimed $5, and keeping their collaborators' data intact are all required at the same time.

## 2. Decisions

**Re-registration stays allowed.** A returning user gets a working account, just not a second welcome grant. No deny list.

**The grant is keyed to an identity, not to a user row.** A separate table records which identities have claimed, and it is never cascaded by user deletion.

**Google `sub` is the only identity source in v1.** Production runs `AUTH_TYPE=GOOGLE`, so `sub` covers every account that can cost money. It is stable per Google account and immune to email spelling, which removes per-provider email normalization from scope entirely.

**Self-hosted stays ungated.** `AUTH_TYPE=LOCAL` installs produce no identity key, so they keep granting the default balance. That is correct: the operator funds their own inference, and there is nothing to farm.

**Only a keyed hash is retained.** HMAC-SHA256 under the existing `SECRET_KEY`, never a raw provider id or email. Under ICO guidance this is pseudonymisation, not anonymisation, so it stays disclosed in the privacy policy as a legitimate-interest retention (fraud prevention, GDPR Recital 47).

**No grace period.** Deletion is immediate and irreversible. Lockout is synchronous; the heavy erase runs in Celery within seconds, matching how workspace deletion already works. A recovery window, if wanted later, is additive.

**Ownership transfer ships as part of this work, and deletion never resolves ownership silently.** The user is shown exactly which workspaces block deletion and chooses, per workspace, whether to hand it to a named member or destroy it. No auto-promotion, no surprise inheritance.

### Rejected

| Option | Why not |
| --- | --- |
| Block re-registration by email | Punishes legitimate returners; the ask was to allow return without the grant. |
| Device fingerprint / IP clustering | Personal data under Recital 30, VPN false positives, new vendor. Solves multi-account farming, a different and unobserved problem. |
| Require a card for the $5 | Kills the "no credit card required" conversion the marketing pages sell. The right lever only once abuse is measured. |
| Email normalization (Gmail dots, `+tags`) | Not needed while Google is the only production login. Written the day password auth is enabled, as one new source function. |
| Plaintext email on a tombstone | More PII than the job needs. |
| Auto-promote the longest-tenured member | Silent. The successor inherits responsibility they never accepted, and the departing user never sees what happened to their team's data. |
| Block deletion until ownership is transferred elsewhere | Would be correct only if transfer existed. Building transfer is what makes blocking humane, so the two ship together. |

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

## 4. Workspace ownership transfer

A standalone feature that account deletion depends on. It also fixes an existing dead end: `leave_workspace` tells owners to "Transfer ownership first or delete the workspace", but no transfer path exists — `is_owner = True` is only ever set at workspace creation, and both `update_member_role` and `remove_member` refuse to touch an owner.

### Ownership is two columns, not one

- `workspaces.user_id` — `ForeignKey("user.id", ondelete="CASCADE")`, non-nullable.
- `workspace_memberships.is_owner` — the RBAC flag the routes check.

A transfer that moves only `is_owner` is cosmetic: the FK still points at the departing user, so their deletion cascades the workspace away regardless. **Both must move in one transaction.** Because `user_id` is non-nullable, there is no "ownerless" state to fall back to; every transfer names a successor.

### Endpoint

`POST /workspaces/{workspace_id}/transfer-ownership`, body `{ "membership_id": <int> }`.

Authorization is the current owner's own `is_owner` flag, not a role permission. Ownership carries the billing and lifecycle consequences of the workspace, so it is not delegable through `MEMBERS_MANAGE_ROLES`.

In one transaction:

1. Verify the caller owns the workspace and the target membership belongs to it and is not the caller.
2. Target membership: `is_owner = True`, `role_id` = the workspace's Owner role.
3. Caller's membership: `is_owner = False`, role unchanged — they keep their permissions and simply stop being the owner, which is the smallest change and lets them subsequently use `leave_workspace`.
4. `workspaces.user_id` = target user id.
5. Write a `Notification` to the new owner naming the workspace and the previous owner.

### Frontend

The team page already separates `owners` from `nonOwnerMembers` and renders a per-member action menu gated on permissions. Add "Transfer ownership" to that menu, visible only to the current owner, with a confirmation naming the recipient and stating that the action cannot be undone by the departing owner.

## 5. Account deletion

### Preflight

`GET /users/me/deletion-preflight` returns the workspaces that block deletion: those the user owns that still have other members. Each entry carries workspace id, name, and the candidate members (id, display name, email) so the UI can render a picker without N further calls.

### Route

`DELETE /users/me` in `app/routes/users_routes.py`, behind `require_session_context` so a leaked PAT cannot destroy an account.

The route re-runs the preflight check server-side and returns `409` with the same payload if anything still blocks. The UI check is a convenience; this is the guarantee. A shared workspace is never destroyed as a side effect of someone leaving.

When clear, synchronously: set `is_active = False` and revoke all refresh tokens via the existing `revoke_all_user_tokens`. That is the entire lockout — `get_auth_context` already gates both the session and PAT paths on `user.is_active`, so no new column and no auth changes are needed. Then enqueue the erase task, clear the session cookie, and return `204`.

Nothing about deletion touches `identity_claims`: the claim was written at grant time and simply survives.

### Erase task

`delete_user_task`, with the retry/backoff options used by `delete_workspace_task`. Steps, in order:

1. Re-assert that no owned workspace has other members. The preflight could have gone stale between the request and the task; a workspace that gained a member in that window is skipped and logged rather than destroyed.
2. For each remaining owned workspace, call the existing `_delete_workspace_background(workspace_id)` — batched chunk and document deletion, `purge_document_blobs`, then `drop_workspace_store`. Reusing this is the point: raw FK cascade from `user` would drop workspace rows while orphaning blobs and git trees.
3. Best-effort delete the Stripe customer when `stripe_customer_id` is set. Charges and invoices stay at Stripe under GDPR 17(3)(b); Stripe is the system of record for tax.
4. Delete the user row. Existing cascades handle memberships, notifications, prompts, PATs, refresh tokens, incentive tasks, OAuth accounts, and purchases.

Idempotent throughout, so a retry after a partial run completes rather than failing. If the task exhausts retries the account is locked out with data intact and the failure is visible in Celery — recoverable, unlike a half-cascade.

### Retained after deletion

The `identity_claims` row (welcome-grant control). Stripe-side charges and invoices (tax). Workspaces transferred to other members. Nothing else.

## 6. Deletion UI

Danger zone at the bottom of `user-settings/profile`, using the existing shadcn dialog and the `userSettings` i18n namespace.

On open, call the preflight. If workspaces block, the dialog lists them and requires a resolution for each — transfer to a chosen member, or delete this workspace — wired to the transfer endpoint and the existing workspace delete route. The account-delete button stays disabled until every entry is resolved.

Final confirmation requires typing `DELETE` and states: permanent and immediate; chats, documents, connectors, and API keys are destroyed; remaining credit is forfeited and not refunded; a new account with the same Google identity will not include the $5 welcome credit.

On success, clear client state and redirect to the marketing home.

## 7. Policy

Privacy policy section 7 gains: deletion is self-serve in Settings; deletion is immediate; we retain a one-way keyed hash of your account identifier solely to prevent re-issue of promotional credit (legitimate interest); Stripe retains invoices for tax.

## 8. Tests

- **Welcome credit:** same Google `sub` twice grants `$5` then `$0`; a user with no OAuth account still grants `$5` and logs the ungated warning; `people/<sub>` and bare `<sub>` resolve to one key.
- **Transfer:** moves both `is_owner` and `workspaces.user_id`; non-owners are rejected; the old owner can then leave; the new owner is notified.
- **Deletion:** returns `409` while a shared owned workspace is unresolved; deactivates and revokes tokens when clear; rejects the PAT path; the erase task removes the user and their solo workspaces, leaves transferred workspaces intact, and is safe to run twice.

## 9. Follow-ups

**`CreditPurchase` cascade.** Purchase rows are `cascade="all, delete-orphan"` and vanish with the user. Accepted: Stripe retains the authoritative charge record. Revisit if local invoice history is ever needed for accounting.

**Daytona sandboxes.** Labeled per thread, not per user, so deleting threads leaves sandboxes to provider TTL. Out of scope; add a best-effort kill if it shows up as cost.

**PostHog person deletion.** `distinct_id` is `str(user.id)`, so a person object survives. Needs a PostHog API call not currently wired.

**Retire the `people/` fallback.** Once the backfill confirms zero `oauth_account` rows matching `people/%`, the legacy branch in `resolve_google_user` and the strip in `_google_sub` can both go.
