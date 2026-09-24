# ADR 0010: Studio models emit structured content and trusted builders render it, so no model-written code runs

- **Status:** Accepted; the rule that no model-written code runs is superseded by [ADR 0028](0028-model-written-code-runs-with-approval.md)
- **Date:** 2026-09-07
- **Source:** [Studio worker plan L8–43](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/worker/04-studio.md#L8-L43), [Pivot plan L261](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L261), [Pivot plan L53](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L53), [Pivot plan L62–63](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L62-L63)

## Context

The hosted Studio lets the model write code, runs it in a network-denied sandbox, checks the result with a vision model and signs a receipt. The desktop app has no Docker and no sandbox. Generation runs on the user's machine, unsandboxed; that risk was accepted, and sandboxed generation is on the enterprise roadmap. Studio as built is in [studio](../architecture/studio.md).

## Decision

- The generation model emits JSON or markdown in the format's schema, and a committed per-format builder renders it with an ordinary library. Nothing the model wrote executes, which turns the accepted risk from "arbitrary code" into "malformed JSON".
- The Image format is the one exception: its selected image model returns the image bytes itself, through the OpenAI-compatible Images API.
- Interactive HTML is shown in a sandboxed iframe.
- There is no sandbox, no Docker and no receipt. A builder's output is deterministic and always a valid file.

## Consequences

- A new format is a builder plus a viewer, and persistence does not branch on the format. In code that is a new folder, one `case` in [`worker/studio/job_router.py`](../../surfsense_local/backend/worker/studio/job_router.py), and its entry in [`modules/artifacts/formats.py`](../../surfsense_local/backend/modules/artifacts/formats.py).
- Every artifact lands the same way, as an `ARTIFACT` document plus its sidecar and files, `ready` or `failed` ([ADR 0003](0003-artifacts-as-documents.md)).
- This is what lets Studio fit an offline app with no Docker that runs on weak local models: the model only has to emit JSON or markdown.

## Where the code stands

- DOCX, PPTX, XLSX and PDF do not follow the rule. Their prompts ask the model to "write one standalone Python script", and [`worker/studio/office/runner.py`](../../surfsense_local/backend/worker/studio/office/runner.py) runs the reply with `exec()` in the worker process, unsandboxed, bounded by a 120-second timeout that cannot hard-kill a runaway thread. The module's `ponytail:` comment names that ceiling, and an out-of-process sandbox runner as the upgrade path. For these four formats the risk is back at arbitrary code with the worker's privileges.
- The other eight formats (summary, mind map, flashcards, quiz, HTML, podcast, image and infographic) execute nothing the model wrote.
- The HTML viewer renders into `<iframe sandbox="allow-scripts allow-popups">` ([`features/studio/viewers/html-viewer.tsx`](../../surfsense_local/frontend/src/features/studio/viewers/html-viewer.tsx)).
