# Contracts

A contract is a frozen file describing something that crosses from one tree to another. Each side builds and tests against the file and its fixture, not against the other side's code. These four were frozen for the 2.0 launch.

| # | Contract | Producer | Consumer | In use since |
|---|---|---|---|---|
| 1 | [License file](01-license-file.md) | `surfsense_backend` license routes | `surfsense_local` license module | 2.0.0 |
| 2 | [Scraper API auth](02-scraper-api-auth.md) | `surfsense_backend` capabilities routes | the paid scraper plugin and `surfsense_mcp` | not yet; neither side is built |
| 3 | [Export bundle](03-export-bundle.md) | `surfsense_backend` export | `surfsense_local` import | 2.0.0 |
| 4 | [Sunset flag](04-sunset-flag.md) | `surfsense_backend` `/health` | legacy desktop v0.0.40, whose source is at tag `archive/hosted-2026-09` | v0.0.40, 12 Sep 2026; the flag reads `true` from T-0, 18 Sep 2026 |

## Fixtures

- `export-sample/` is an unzipped contract-3 bundle. Tests zip it in a setup step. Check it with `python3 check-export-sample.py`.
- `license-sample/` holds contract-1 files signed by a **test** key, plus the generator that makes them. Regenerate and self-check with `node license-sample/generate.mjs`.

Both checks are dependency-free and run from this folder.

Five tests read files in this folder by path. `surfsense_local/backend/tests/integration/migration/test_import.py`, `surfsense_local/backend/tests/integration/license/test_license.py` and `surfsense_backend/tests/unit/services/test_account_export.py` read the fixtures; `surfsense_backend/tests/integration/test_account_export.py` runs `check-export-sample.py` against a real export; and the release build's test-key guard, `surfsense_local/backend/tests/packaging/test_license_key.py`, reads the test public key. Moving this folder means updating all five in the same change, plus the skip entry in `scripts/check_docs.py` and the `docs/contracts/**` path filters in `.github/workflows/docker-tests.yml` and `.github/workflows/desktop-tests.yml`.

## Changing a contract

A contract changes by a pull request that the owners of both sides approve. [CODEOWNERS](../../.github/CODEOWNERS) requests their review, but GitHub accepts one approval, so the second is by agreement. If the change is not backward compatible, bump the version field the contract names (`format` for the bundle, the `alg`/field list for the license file) and update the fixture in the same PR. Never change a fixture without changing the contract text that describes it.
