# Architecture decision records

Each file here records one decision and the reasons for it: the why behind what [`architecture/`](../architecture/overview.md) describes. An accepted ADR is not rewritten. When a decision changes, a new ADR supersedes the old one, and the only edits an accepted ADR takes are its Status line, which becomes "Superseded by" with a link to the new record (or, when only part is superseded, names that part and the record that supersedes it), and fixes to its links.

## Adding one

Take the next free number. Add the record in the same pull request as the change it decides, or with the proposal that makes it. Use this shape and keep it short:

```markdown
# ADR NNNN: <the decision, stated as a sentence>

- **Status:** Accepted
- **Date:** YYYY-MM-DD
- **Supersedes:** <only if it does>
- **Source:** [<short name> L<a>–<b>](<permalink>)

## Context
<the problem and the constraints that forced a choice>

## Decision
<the choice, precisely; bullets are fine>

## Consequences
<what it makes true, what it costs, what it rules out>

## Where the code stands
<only when the code does not fully hold the decision; state the gap plainly, citing file paths>
```

The Date is the day the decision was first written down. Source links are permalinks to a fixed commit, so they keep working after the file they point at moves or is deleted.

## Numbering

0001 and 0002 were hosted-era records about the git-native knowledge base. They were deleted on 17 Sep 2026 in commit [35c83caa8](https://github.com/MODSetter/SurfSense/commit/35c83caa82b806fda1aa1ed8391b246b683c59fc), and their numbers are retired. 0003 was written for the hosted stack and restored for the desktop app.

## Index

| Number | Title | Status |
|---|---|---|
| 0003 | [Generated deliverables are a document type, not a second corpus](0003-artifacts-as-documents.md) | Accepted |
| 0004 | [The desktop app is its own tree on FastAPI, SQLite and Huey, with no accounts](0004-desktop-app-is-its-own-tree.md) | Accepted |
| 0005 | [Schema changes are hand-written Alembic revisions that the API applies at startup](0005-hand-written-migrations.md) | Accepted |
| 0006 | [Retrieval widens recall with FTS5 and sqlite-vec, then orders the union by cosine similarity](0006-hybrid-retrieval.md) | Accepted |
| 0007 | [Embeddings come from a bundled bge-small model run in process on the CPU](0007-bundled-embeddings.md) | Accepted |
| 0008 | [Ingest and Studio jobs run on separate Huey queues, each drained by its own worker](0008-two-job-queues.md) | Accepted |
| 0009 | [The UI stays fresh by invalidating queries on server-sent events, with no sync engine](0009-freshness-by-invalidation.md) | Accepted |
| 0010 | [Studio models emit structured content and trusted builders render it, so no model-written code runs](0010-studio-builders-not-sandboxes.md) | Accepted |
| 0011 | [llama-server in router mode is the one local model runtime](0011-llama-cpp-local-runtime.md) | Accepted, in part superseded by 0026 |
| 0012 | [The GPU backend is Vulkan everywhere off Apple Silicon, with no CUDA payload](0012-vulkan-only-gpu-backend.md) | Accepted |
| 0013 | [Model fit comes from the allocator's view of one device, and only physics refuses an install](0013-fit-from-the-allocator.md) | Accepted |
| 0014 | [The model catalog is a curated offline manifest plus Hugging Face search, and SurfSense downloads the files itself](0014-two-tier-model-catalog.md) | Accepted, in part superseded by 0026 and 0027 |
| 0015 | [Remote models come through named OpenAI-compatible connections, discovered live](0015-openai-compatible-connections.md) | Accepted |
| 0016 | [The app sends no telemetry or crash reports](0016-no-telemetry.md) | Accepted |
| 0017 | [Every outbound destination is off until the user allows it](0017-egress-off-by-default.md) | Accepted, in part superseded by 0027 |
| 0018 | [Provider keys are encrypted with a per-install secret kept in the OS keychain](0018-keychain-envelope-encryption.md) | Accepted |
| 0019 | [Licenses are signed files verified offline, and they gate only plugins and priority support](0019-offline-licenses.md) | Accepted |
| 0020 | [The new app and the legacy app share one release feed and are kept apart by update channel](0020-two-update-channels.md) | Accepted |
| 0021 | [There is no Intel Mac build](0021-no-intel-mac-build.md) | Accepted |
| 0022 | [Hosted accounts move to the app as a markdown-only export that is re-embedded locally](0022-markdown-only-cloud-import.md) | Accepted |
| 0023 | [Every hosted sunset behaviour sits behind a runtime flag, and nothing is deleted or redirected unconditionally](0023-sunset-behind-flags.md) | Accepted |
| 0024 | [The license portal has no accounts and no license tables; Stripe and Keygen are the system of record](0024-portal-without-accounts.md) | Accepted |
| 0025 | [The hosted scraper API client ships as a paid plugin whose source lives in this repo](0025-scraper-client-as-paid-plugin.md) | Accepted |
| 0026 | [Curated models are ordered by their position in the manifest, with no score](0026-curated-order-is-list-position.md) | Accepted |
| 0027 | [Egress consent is per host, so model search and downloads share one](0027-egress-consent-per-host.md) | Accepted |
