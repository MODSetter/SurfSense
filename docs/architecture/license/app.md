# License in the desktop app

The desktop app imports a Keygen license file and verifies it offline, against Ed25519 public keys compiled into the binary, and never contacts Keygen. A license is meant to unlock paid plugins, which are not built yet, and priority support, and a trial the same for its term; in the app today it changes only what Settings and the sidebar show. No state of the license ever disables the app. The check on the machine is honesty for the interface, not enforcement: the app is public and can be rebuilt without it, so enforcement belongs to the servers a paid plugin calls.

**Code:** [`surfsense_local/backend/modules/license/`](../../../surfsense_local/backend/modules/license/), [`surfsense_local/frontend/src/features/license/`](../../../surfsense_local/frontend/src/features/license/)
**Decisions:** [ADR 0019](../../adr/0019-offline-licenses.md)

The file format is [contract 1](../../contracts/01-license-file.md); the hosted side that issues files is the [portal](portal.md).

## What the license gates

Paid plugins and priority support, nothing else, and neither is in the app yet: plugins are a proposal, and priority support is offered in the license email. Expiry stops those two and leaves the app, its data and its updates alone. Updates are free for everyone and the updater has no license logic: with public installers, an expired user could delete the license file and become a free user, so gating updates would be theater. `maxUsers` is shown, never enforced.

The [plugins proposal](../../proposals/plugins/README.md) specifies that a paid plugin installs and runs only with an unexpired license, a trial included. Inside the app, Settings and the sidebar are what read the license state.

## Verifying a file

`verify()` in `verify.py` follows contract 1's consumer steps in order and stops at the first failure:

1. Strip the PEM markers and whitespace and base64-decode the JSON; anything unreadable is `not_a_license_file`.
2. An `alg` other than `base64+ed25519` is `unsupported_algorithm`.
3. The signature over `"license/" + enc` must verify with one of the compiled keys, or the file is `bad_signature`. `enc` is not decoded until this passes.
4. `meta.issued` more than `MAX_CLOCK_DRIFT`, five minutes, in the future is `clock_untrusted`; a non-null `meta.expiry` in the past is `file_expired`. The portal checks files out with `meta.expiry: null`.

The five minutes are there because a laptop clock running a few minutes fast is not tampering. A passing file yields its key, plan, email, license expiry, `maxUsers` and `meta.issued`. `PUT /license` answers a rejection with 422 and `{code, message}`; the messages are in `router.py`.

`KEYGEN_PUBLIC_KEYS_HEX` is a tuple, newest first, and a file signed by any key in it is accepted. Rotating the Keygen account key is therefore a release that trusts both keys, not a recall of every license already issued. The keys are source code, never read from configuration, environment or disk; tests swap in the fixture key by patching the constant.

## State

The singleton row `license_state` holds the file as imported, when it was imported, and `clock_watermark`. The state is re-derived from the stored file on every read:

| State | When |
|---|---|
| `none` | no file is stored |
| `active` | the license expiry is in the future |
| `license_expired` | the license expiry has passed; the file stays stored and shown |
| `clock_untrusted` | the clock is more than five minutes behind the watermark, whatever the expiry |

Every import, and every status read of a stored file that verifies, moves the watermark to `max(watermark, now, meta.issued)`. A clock wound back therefore reads as `clock_untrusted` until time catches up, instead of reviving an expiring license. The watermark lives in SQLite the user can edit, so a `ponytail:` comment calls it honesty for the UI, not enforcement.

There is one slot: importing a valid file replaces whatever was stored. That is what contract 1's rule 7 needs, since a resend checks out a fresh file for the same license with a later `meta.issued`, and it takes the old one's place.

| Route | Does |
|---|---|
| `GET /license/status` | answers `state`, `plan`, `email`, `expiry` and `max_users` |
| `PUT /license` | verifies `{certificate}`, stores it and answers the new status |
| `DELETE /license` | forgets the file; the state returns to `none` |

## Settings and the sidebar

Settings › License adds a license by choosing a `.lic` file or pasting its text, which the renderer sends to `PUT /license`. It shows the plan, the email, "Expires" or "Ended" with the date, the seat count when there is one, and Replace and Remove buttons, plus a notice when the clock is off, when the license has expired, and when it runs out within 14 days. The sidebar footer carries one status row: green for `active`, red for every state that leaves plugins locked.

## The compiled key

The release workflow's step "Refuse to build with the test signing key" runs `tests/packaging/test_license_key.py` before it freezes anything. The test fails when the fixture key in [`docs/contracts/license-sample/public-key.hex`](../../contracts/license-sample/public-key.hex) is among the compiled keys: the fixture files are signed from a seed that is public in the repo, so shipping that key would let anyone sign a license. `pyproject.toml` excludes the `packaging` marker by default, and the step's own `-m packaging` wins ([packaging](../packaging.md)). The test proves only that the fixture key is absent.

## Known gaps

- Settings has no "Start trial" or "Buy" link, and its expired-license notice says to renew "from your account", which the portal does not have.
- A stored file whose `meta.issued` is more than five minutes ahead of the clock makes `GET /license/status` fail with 500 instead of answering `clock_untrusted`: `status()` re-runs `verify()`, and nothing catches its rejection.
