# Phase 2 — Sandbox + PDF

**Status:** Complete. Phase 3 superseded the original model-orchestrated verification mechanism with backend-owned `verify_artifact`; no compatibility path remains.
**Parent spec:** [`artifacts-overhaul.md`](./artifacts-overhaul.md).
**Depends on:** phase 1 artifact persistence and API.

## 1. Shipped scope

- Provider-neutral sandbox protocol with OpenSandbox for self-hosting and Daytona for cloud.
- Per-thread lazy sessions, rediscovery, renewal, idle reaping, recovery, and workspace concurrency caps.
- Polyglot sandbox image with network denied at runtime and authoring/rendering dependencies preinstalled.
- `execute` and UTF-8-only `read_sandbox_file`.
- PDF skill and format routing.
- Binary `save_artifact` flow using `Artifact`/`ArtifactFile` over an artifact `Document`.
- `PdfFileViewer` registered for PDF primary files.

The measured OpenSandbox spike passed: metadata rediscovery, timeout renewal, binary read, and steady warm execution were verified against the selected image/server.

## 2. Current PDF flow

1. The deliverables agent calls `load_artifact_instructions("pdf")` to load the sandbox skill.
2. Source code generates a deliverable-named PDF in the sandbox.
3. `verify_artifact(path)` performs the current phase-3 verification service.
4. `save_artifact(path, title, markdown_representation, ...)` validates the signed receipt and persists the artifact.
5. The result returns `artifact_id` and `generation`.
6. The artifact panel fetches the dedicated manifest and renders the primary PDF.

For revision, the agent calls `load_artifact_for_revision(artifact_id)`, which restores the current PDF for reference plus Markdown context. The PDF is regenerated and saved with the same `artifact_id` and returned `expected_generation`. Missing or stale generation is rejected.

## 3. Persistence and search assumptions

- Metadata and blobs are durable in the save tool call.
- Binary keys are under the artifact storage namespace; generation source remains a transient sandbox input rather than an `ArtifactFile` role.
- The searchable Markdown is the artifact's `Document`, committed under `/documents/**` and indexed asynchronously on Git-backed workspaces.
- Non-git workspaces index it through the document pipeline inside the save; an indexing failure leaves a durable artifact with a failed document for reindex.
- Search and citations are the document ones; the artifact document type routes the citation to the panel.
- Viewer, manifest, download, and cache identity is `artifact_id`.

## 4. Verification note

The phase-2 sentinel, mtime ledger, model-facing image inspection, and skill scripts were temporary implementation history and are deleted. The current invariant is phase 3's signed, byte-bound receipt. A deployment that cannot perform visual review may receive a signed “could not verify” result; an agent that skipped verification cannot save a binary.

## 5. Checks

- Provider create/execute/read/renew/rediscover/terminate contract.
- Session reuse, idle reap, and concurrency-cap behavior.
- PDF generate -> verify -> save -> manifest -> render/download.
- Receipt rejects changed bytes.
- Later-turn revision preserves `artifact_id`, increments generation, and purges superseded blobs.
- A second chat's roster cannot expose the first chat's artifact.
- No prompt or active tool registration routes new work through legacy report/resume tools.
- Phase 8 flashcards reuse the same load-instructions, execute, verify, and
  save tools; they do not introduce a format-specific agent tool.

## 6. Exit criteria

1. PDF creation has no Typst dependency.
2. Generated PDF bytes persist as the primary artifact file; generation source is transient.
3. The primary renders via the artifact API with immutable caching and downloads with its generated filename.
4. The artifact becomes searchable according to Git/non-git indexing timing.
5. Revision updates one artifact under optimistic generation rather than producing a second deliverable.
6. Future programmatically verified formats can skip rendered review without
   weakening the signed primary-byte receipt.
