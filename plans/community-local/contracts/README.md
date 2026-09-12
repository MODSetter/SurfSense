# Contracts between workstreams

A contract is a frozen file describing something that crosses from one workstream to another. Once frozen, each side builds and tests against the file and its fixture, not against the other side's code. The two sides meet once, at the end-to-end sync named in [`../00d-pivot-plan.md`](../00d-pivot-plan.md).

| # | Contract | Producer | Consumer | Exercised |
|---|---|---|---|---|
| 1 | [License file](01-license-file.md) | Dev B (`surfsense_backend` license routes) | Dev A (`surfsense_local` license module) | v1.0.0 |
| 2 | [Scraper API auth](02-scraper-api-auth.md) | Dev A (app scraper client) | Dev B (`surfsense_backend` capabilities routes) | T+7 |
| 3 | [Export bundle](03-export-bundle.md) | Dev B (`surfsense_backend` export) | Dev A (`surfsense_local` import) | v1.0.0 |
| 4 | [Sunset flag](04-sunset-flag.md) | Dev B (`surfsense_backend` `/health`) | Dev A (legacy `surfsense_desktop` v0.0.40) | T-0 |

## Fixtures

- `export-sample/` is an unzipped contract-3 bundle. Tests zip it in a setup step. Check it with `python3 check-export-sample.py`.
- `license-sample/` holds contract-1 files signed by a **test** key, plus the generator that makes them. Regenerate and self-check with `node license-sample/generate.mjs`.

Both checks are dependency-free and run from this folder.

## Changing a contract

A contract changes by a pull request that both Dev A and Dev B approve. If the change is not backward compatible, bump the version field the contract names (`format` for the bundle, the `alg`/field list for the license file) and update the fixture in the same PR. Never change a fixture without changing the contract text that describes it.
