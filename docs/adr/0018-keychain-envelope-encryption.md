# ADR 0018: Provider keys are encrypted with a per-install secret kept in the OS keychain

- **Status:** Accepted
- **Date:** 2026-09-14
- **Source:** [Pivot plan L234](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L234), [Connections plan L89–97](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/05b-openai-compatible-connections.md#L89-L97)

## Context

A remote connection's API key has to be usable by the processes that make the calls, the API and the workers, so it cannot live only in Electron. It still should not sit in clear in a SQLite file on the user's disk. Connections as built are in [connections](../architecture/connections.md).

## Decision

- Envelope encryption. Electron keeps one random 32-byte secret per install in `secret.bin`, in its userData directory, encrypted with `safeStorage`, the OS keychain ([`electron/src/main/secret.ts`](../../surfsense_local/electron/src/main/secret.ts)).
- Electron passes the secret as `SURFSENSE_LOCAL_SECRET` to the API and both workers ([`sidecars/python.ts`](../../surfsense_local/electron/src/main/sidecars/python.ts)). llama-server and sd-server do not get it.
- The backend derives a Fernet key from the secret with SHA-256 and stores each provider key encrypted in `provider_connections.api_key_ciphertext` ([`shared/secrets.py`](../../surfsense_local/backend/shared/secrets.py)). Revision `0007` dropped the plaintext `api_key` column.
- The API never returns a key. A connection reads back `has_api_key` only.

## Consequences

- A key is as safe as the OS keychain. On Linux the app calls `safeStorage.setUsePlainTextEncryption(true)`, so on a machine without a keyring daemon it keeps booting on Chromium's built-in key instead of refusing to start ([`electron/src/main/index.ts`](../../surfsense_local/electron/src/main/index.ts)).
- A bare `uv run` without Electron uses a plaintext `secret` file next to the database. It is marked `ponytail:` as the development path.
- If `secret.bin` cannot be decrypted, after a reinstall or a keychain reset, Electron mints a new secret. Every stored key is then unreadable until the user enters it again, while the rows stay intact.
- `decrypt()` raises `UnreadableSecretError` for such a key, and the API answers `409` with the code `unreadable_secret` ([`api/main.py`](../../surfsense_local/backend/api/main.py)): the request is well formed, and only the stored value needs replacing.

## Where the code stands

- `ProviderConnection.api_key` in [`modules/llm/models.py`](../../surfsense_local/backend/modules/llm/models.py) still catches `cryptography`'s `InvalidToken` to read an unreadable key as no key, but `decrypt()` now raises `UnreadableSecretError`, so that fallback never runs. `test_rotated_secret_reads_as_no_key` in [`tests/unit/shared/test_secrets.py`](../../surfsense_local/backend/tests/unit/shared/test_secrets.py) fails on `dev` for that reason.
