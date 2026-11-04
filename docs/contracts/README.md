# Contracts

A contract is a frozen file describing something that crosses from one tree to another. Each side builds and tests against the file and its fixture, not against the other side's code. The first four were frozen for the 2.0 launch.

| # | Contract | Producer | Consumer | In use since |
|---|---|---|---|---|
| 1 | [License file](01-license-file.md) | `surfsense_backend` license routes | `surfsense_local` license module | 2.0.0 |
| 2 | [Scraper API auth](02-scraper-api-auth.md) | the plugin host; `surfsense_backend` capabilities routes | the desktop app; `surfsense_mcp` | plugin host and app since 2.2.1; backend and MCP not built |
| 3 | [Export bundle](03-export-bundle.md) | `surfsense_backend` export | `surfsense_local` import | 2.0.0 |
| 5 | [Desktop telemetry](05-desktop-telemetry.md) | Electron main (the update check and the usage report); `surfsense_local` backend (the local summary) | `www`'s `/api/updates` and `/api/usage` routes; the app's UI (the bridge) | released in 2.2.4; revision 1.1 in 2.2.5 |
| 6 | [Job pack delivery](06-job-pack-delivery.md) | the license server's job-pack route (`backend/license/job_packs/`), and the private pack repository's releases it reads | `surfsense_local` job pack delivery | not released |

## Fixtures

- `export-sample/` is an unzipped contract-3 bundle. Tests zip it in a setup step. Check it with `python3 check-export-sample.py`.
- `license-sample/` holds contract-1 files signed by a **test** key, plus the generator that makes them. Regenerate and self-check with `node license-sample/generate.mjs`.
- `job-pack-sample/` holds a contract-6 pack signed by a **test** key and that key's public half, plus the generator that makes them. Regenerate and self-check from `backend/` with `uv run python ../docs/contracts/job-pack-sample/generate.py`, which needs `cryptography`.

The first two checks are dependency-free and run from this folder.

Seven test files read this folder by path. `surfsense_local/backend/tests/integration/migration/test_import.py` and `surfsense_local/backend/tests/integration/documents/test_every_source_has_a_folder.py` read the export sample; `surfsense_local/backend/tests/license_samples.py`, `surfsense_local/backend/tests/integration/license/test_license.py` and the release build's test-key guard, `surfsense_local/backend/tests/packaging/test_license_key.py`, read the license sample; and `backend/license/tests/test_job_pack_contract.py` and `backend/license/tests/test_job_pack_verify.py`, whose test-key guard reads its public key, read the job pack sample. Moving this folder means updating all seven in the same change, plus the skip entry in `scripts/check_docs.py`, the `docs/contracts/**` path filter in `.github/workflows/desktop-tests.yml`, the `docs/contracts/job-pack-sample/**` path filter in `.github/workflows/plugins-pull-request-checks.yml` and the folder's mount in `.github/workflows/docker-tests.yml`.

## Changing a contract

A contract changes by a pull request that the owners of both sides approve. [CODEOWNERS](../../.github/CODEOWNERS) requests their review, but GitHub accepts one approval, so the second is by agreement. If the change is not backward compatible, bump the version field the contract names (`format` for the bundle, the `alg`/field list for the license file) and update the fixture in the same PR. Never change a fixture without changing the contract text that describes it.
