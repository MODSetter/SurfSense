# ADR 0019: Licenses are signed files verified offline, and they gate only plugins and priority support

- **Status:** Accepted
- **Date:** 2026-09-08
- **Source:** [Pivot plan L3](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L3), [Pivot plan L35–38](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L35-L38), [Pivot plan L43](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L43), [Pivot plan L93](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L93), [Pivot plan L121](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L121), [Pivot plan L233](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L233)

## Context

The app is Apache-2.0, its installers are free and public, and it is paid for through a license. It runs airgapped. A check on the user's machine can be stripped by any fork; the enforcement that holds is the server-side check at the hosted scraper API. The license module as built is in [license/app](../architecture/license/app.md).

## Decision

- License management is Keygen. A license is a signed file ([contract 1](../contracts/01-license-file.md)), checked out perpetual (`ttl: null`) and verified offline with the account's Ed25519 public keys compiled into the app. The file carries the license expiry, renewal is a new file, and the app never contacts Keygen (recorded 12 Sep 2026). There is no machine binding.
- `KEYGEN_PUBLIC_KEYS_HEX` in [`modules/license/verify.py`](../../surfsense_local/backend/modules/license/verify.py) is a tuple. A file signed by any listed key verifies, so rotating the account key is a release that trusts both keys rather than a recall of every license already issued.
- The license gates exactly two things, plugins and priority support. It never disables the app, and expiry stops those two things and nothing else.
- Updates are free for everyone, and the updater has no license logic. Gating updates was rejected: with public installers, an expired user could delete the license file and become a free user with every update, so the gate would be theater.
- A trial license unlocks the same things for its term (decided 22 Sep 2026). The portal's trial term defaults to 30 days (`LICENSE_TRIAL_DAYS` in [`surfsense_backend/app/config/__init__.py`](../../surfsense_backend/app/config/__init__.py)); the pivot plan had specified 14.
- The release build refuses the test signing key. The step "Refuse to build with the test signing key" in [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml) runs [`tests/packaging/test_license_key.py`](../../surfsense_local/backend/tests/packaging/test_license_key.py) before the binaries are frozen.

## Consequences

- Revocation only bites server-side, which is where enforcement belongs; for the scraper API that is license mode ([contract 2](../contracts/02-scraper-api-auth.md)), which is not built yet. The check in the app is UX.
- The account's Ed25519 keypair is the most critical secret. If its private half is lost, files already issued keep verifying, but no shipped binary accepts a new one until a release ships with a new key. The plan requires it to be backed up out of band, apart from the database dump.
- A clock more than five minutes earlier than the highest timestamp the app has seen marks the license `clock_untrusted` until the clock catches up.
- A team key's seat count (`maxUsers`) is informational. Enforcement is the audit clause, not the app.

## Where the code stands

- Nothing in the app gates on the license yet. The plugin system is a proposal ([plugins proposal](../proposals/plugins/README.md)) with no code in the tree, so a license is imported, verified and shown in Settings, and changes nothing else.
