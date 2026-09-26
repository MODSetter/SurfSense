# Contract 1: license file

A Keygen license file. The backend's license routes check out a fresh file at every delivery (producer rule 5) from our **self-hosted Keygen CE** instance over the internal network. The app verifies it forever, offline, with that account's public key compiled into the binary. Nothing about the format below changes with self-hosting — CE is the same API and the same signed-file shape.

## Format

A PEM-style text file, extension `.lic`:

```
-----BEGIN LICENSE FILE-----
<base64, wrapped at 64 columns>
-----END LICENSE FILE-----
```

The base64 decodes to JSON with exactly three fields:

| Field | Meaning |
|---|---|
| `alg` | Must be `base64+ed25519`. Anything else is rejected before any other step. |
| `enc` | Base64 of the payload JSON below. **Not encrypted.** |
| `sig` | Base64 of the Ed25519 signature over the ASCII string `"license/" + enc`. |

The payload (`enc` decoded) is a Keygen JSON:API document. The app reads these fields and ignores everything else, including `included` and `relationships`:

| Path | Type | Meaning |
|---|---|---|
| `meta.issued` | ISO 8601 | When the file was checked out. Must not be in the future. |
| `meta.expiry` | ISO 8601 or `null` | When the **file** expires. Always `null` for us (see producer rules). |
| `data.attributes.key` | string | The license key. Sent to the scraper API as the bearer (contract 2). |
| `data.attributes.expiry` | ISO 8601 | When the **license** expires. |
| `data.attributes.maxUsers` | int or `null` | Seat count for team keys; `null` otherwise. Informational, not enforced. |
| `data.attributes.metadata.plan` | `trial` \| `individual` \| `team` | Which plan. |
| `data.attributes.metadata.email` | string | Licensee email, shown in Settings. |

## Producer rules (`surfsense_backend` license routes)

1. Create the license under the matching policy with `metadata: {"plan": ..., "email": ...}`. For team keys set the `maxUsers` override to the Stripe quantity. Stripe purchases also carry `stripeCustomerId` and `checkoutSessionId` in metadata; the app ignores both, and they exist because Keygen metadata is the only lookup index we have (there is no license table). Trial licenses additionally get an explicit `expiry` rather than the policy default, so a trial issued before the plugin ships is not eaten by the gap week.
2. Check out with `POST /licenses/{id}/actions/check-out` and body `{"meta": {"ttl": null}}`. **The default TTL is 30 days.** The app never refreshes, so a default-TTL file dies a month after purchase. `ttl: null` produces `meta.expiry: null`.
3. Do not pass `encrypt`. Do not pass `include`.
4. Serve the certificate string as-is; do not re-wrap or reformat it.
5. **Certificates are not stored.** Every delivery — success page, purchase email, resend — checks out a fresh file for the same license. Two files for one license therefore differ in `meta.issued` and are byte-different, while `data.attributes.key` and `expiry` stay identical. This follows from Stripe and Keygen being the only system of record.

## Consumer rules (`surfsense_local` license module)

Verify in this order and stop at the first failure:

1. Strip the header and footer lines and all whitespace; base64-decode. Not decodable → `not_a_license_file`.
2. `alg != "base64+ed25519"` → `unsupported_algorithm`.
3. Verify `sig` over `"license/" + enc` with the compiled-in public key. Fails → `bad_signature`. **Do not read `enc` before this step passes.**
4. Base64-decode `enc`, parse JSON.
5. `meta.issued` later than now → `clock_untrusted`. `meta.expiry` non-null and past → `file_expired`. The app allows five minutes of drift in the first check (`MAX_CLOCK_DRIFT` in `surfsense_local/backend/modules/license/verify.py`), since a laptop clock a few minutes fast is not tampering.
6. `data.attributes.expiry` past → `license_expired`. This is a state, not a rejection: the file is still stored and shown, with the plan marked expired.

Then persist the parsed fields and update the clock watermark (highest timestamp ever seen; a clock earlier than the watermark marks the license `clock_untrusted` until it catches up).

7. **A file may be replaced by another file for the same key.** Producer rule 5 means a resend produces a fresh certificate with a later `meta.issued` for a license already imported. Importing it replaces the stored file and advances the watermark; it is never treated as a second license or rejected as a duplicate. Match on `data.attributes.key`, not on file bytes.

The public key is **hard-coded in the app source**, never read from config, environment, or a file at runtime. Tests inject the test key from `license-sample/public-key.hex` through a test-only seam.

Reference implementation: [keygen-sh/example-python-cryptographic-license-files](https://github.com/keygen-sh/example-python-cryptographic-license-files). Port it to the `cryptography` package (`Ed25519PublicKey.from_public_bytes`); the `ed25519` PyPI package it uses is unmaintained.

## Fixture

`license-sample/` is produced by `generate.mjs` from a fixed seed, so re-running it is byte-identical:

| File | Plan | State |
|---|---|---|
| `individual.lic` | individual | valid |
| `team.lic` | team, `maxUsers: 12` | valid |
| `trial.lic` | trial | valid |
| `expired.lic` | individual | `license_expired` |
| `public-key.hex` | | raw 32-byte Ed25519 public key, hex, as the Keygen account reports it (`Account.sole.ed25519_public_key`) |

These are signed by a **test** key, not the production key. Once the Keygen CE instance is up, add one real `keygen-individual.lic` and its public key for an integration check; keep the test files for unit tests.

## Tests each side owns

- Backend: a Stripe-test-mode purchase yields a file whose `meta.expiry` is `null` and whose `metadata.plan` and `metadata.email` match the checkout. A resend for the same email yields a file with the same `key` and a later `meta.issued`.
- App: every fixture file parses to the expected plan and state; a one-byte change to `enc` fails with `bad_signature`; `expired.lic` yields `license_expired`.
