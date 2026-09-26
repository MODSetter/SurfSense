---
status: accepted
code:
  - surfsense_local/backend/modules/agent/
  - surfsense_local/backend/modules/egress/
  - surfsense_local/backend/modules/documents/
  - surfsense_local/backend/worker/studio/
  - surfsense_local/backend/worker/ingestion/
  - surfsense_local/electron/scripts/
  - surfsense_local/electron/src/main/sidecars/
  - surfsense_local/frontend/src/features/chat/
---

# The agent

> The selected text model decides how SurfSense works on the user's sources. A model that is tested with opencode drives a bundled opencode over SurfSense's own tools. Every other model runs fixed workflows that SurfSense orchestrates with structured output. Outputs come first: nothing in this proposal edits the user's files.

Today's chat is single-pass grounded chat with no tools ([chat](../../architecture/chat.md)), and Studio turns sources into artifacts ([studio](../../architecture/studio.md)). The [model catalog proposal](../model-catalog.md) leaves "an agent loop, where chat hands the model tools" to "a later chat rework with its own proposal". This is that proposal.

Every fact here links to where it was checked: this repo, opencode `v1.18.32` (commit `545f51d`), llama.cpp `b11050` (the build the app pins), or a named external source, as of 23 Sep 2026. Anything not yet known is listed under Open questions rather than stated.

## Workstreams

| Stream | File | Owns | Starts from |
|---|---|---|---|
| **Engine choice** | [`01-which-engine.md`](01-which-engine.md) | which engine a selected model gets | the capability data the catalogs already carry |
| **Tools** | [`02-tools.md`](02-tools.md) | search, read and create-artifact functions both engines call | functions that exist today |
| **opencode** | [`03-opencode.md`](03-opencode.md) | packaging, launch, network lockdown, permissions, working folders | the tools, and the egress proxy it specifies |
| **Workflows** | [`04-workflows.md`](04-workflows.md) | Studio's structured output, the formatting pass, the text fallback | nothing; can start now |
| **Sources folder** | [`05-sources-folder.md`](05-sources-folder.md) | linking a folder on disk as the Sources root | nothing; independent |

Suggested order: tools, then workflows and the sources folder in parallel, then opencode, then the engine choice that routes between them.

## Locked decisions

| Decision | Choice |
|---|---|
| Engines | Two. opencode for a model on a tested list; fixed workflows for every other model. |
| Who gets opencode | Only models on the tested list. The list starts empty. Nanbeige4-3B-Thinking and xLAM-2 are not candidates. |
| Reading files a model cannot read | Docling's extracted text, which ingestion already produces. |
| Shipping opencode | Inside the installer, pinned by version and SHA-256 at build time. |
| Installer and network | The installer downloads nothing. Anything fetched later is fetched by the running app after egress consent. |
| opencode and the network | No outbound connection without egress consent: its fetches are switched off, its dependencies are shipped, and its HTTP goes through a backend proxy that calls `egress.require()`. |
| Remote model keys | opencode reaches remote models only through SurfSense, so keys stay in SurfSense. |
| Model-written code | Runs on the user's machine without a sandbox; the agent asks before every shell command ([ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md)). A sandbox is later work for licensed users. |
| Undo | Not in this phase. opencode snapshots are off, and the agent writes only inside SurfSense's own output folder. |
| Sources on disk | A linked folder is indexed in place and watched. Git is not the storage. |

## Out of scope

Editing sources or artifacts, undo, git history, figure and image understanding, a sandbox, output-quality work beyond what [`04-workflows.md`](04-workflows.md) marks to build, and prompt tuning. The research behind the later items is recorded in the stream files so it is not repeated.

## Open questions

Each stream file lists its own. These cut across them:

- Where the agent sits in the UI relative to today's chat: the same thread view with the engine chosen per model, or a separate entry.
- What "tested" means for the opencode list: the [chat eval](../chat-eval.md) extended to agent tasks, or a manual checklist, and who maintains the list.
- Whether Studio's Office formats should also ask before running model-written code ([ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md)).
