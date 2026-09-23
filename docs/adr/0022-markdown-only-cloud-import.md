# ADR 0022: Hosted accounts move to the app as a markdown-only export that is re-embedded locally

- **Status:** Accepted
- **Date:** 2026-09-08
- **Source:** [Pivot plan L73–75](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L73-L75), [Pivot plan L230](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L230), [Pivot plan L313](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L313), [Pivot plan L326](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L326)

## Context

Moving the hosted service's current users onto the desktop app is the point of the pivot, so export and import had to ship together, in 2.0.0. At launch the hosted service became export-only for a 30-day tail, after which user content is purged. Import as built is in [import](../architecture/import.md).

## Decision

- The export is one ZIP for the whole account, markdown only ([contract 3](../contracts/03-export-bundle.md)): every ready document's extracted content with its folder structure and title, plus the chat threads. Original uploads and old generated artifacts stay behind. Tool calls and agent steps are dropped, and citations are reduced to document titles.
- Import is a bulk upload on the API side, and nothing touches the network. It creates one local workspace per hosted workspace, writes each markdown file through the upload path so it gets a `dedup_key`, keeps `folder_path`, `source` and the hosted ids in `document_metadata`, and enqueues the existing `ingest_document` ([`modules/migration/`](../../surfsense_local/backend/modules/migration/)).
- The app re-chunks and re-embeds everything locally. Markdown is in `TEXT_SUFFIXES` ([`worker/ingestion/parsing.py`](../../surfsense_local/backend/worker/ingestion/parsing.py)), so Docling is skipped and import is chunk and embed only.
- An imported assistant message keeps its citations as a "Sources: A, B" line in its text, because local citations are chunk-backed and imported ones cannot be.

## Consequences

- The migration is lossy by design. The export step on the `/sunset` page says so, and the info tooltip beside Import from SurfSense cloud in the app's Settings says original files and generated artifacts stay behind.
- Re-running a bundle is safe for documents. `dedup_key` skips each one already imported, and each workspace is found again by its `cloud_id`. A re-export after edits lands as a second copy, not an update.
- Chat threads carry no dedup key, so they import only with a workspace's first import. The `ponytail:` in [`modules/migration/service.py`](../../surfsense_local/backend/modules/migration/service.py) names the upgrade: a hosted thread id column on `chat_threads`.
- A large account is embed-bound on a laptop: minutes to an hour for thousands of documents, in the background.
- Migrating original files would be a `format` bump on contract 3, if users ask for it.
