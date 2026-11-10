# The render that waits

> A document that names a picture still being drawn is not refused. It becomes a pending version that the last of its pictures' jobs queues, so a comic drawn on a slow local model still ends as a PDF without the user asking again.

Amends [ADR 0087](../../adr/0087-the-agent-makes-pictures-with-its-own-surfsense-tool.md)'s "A document needing a picture still being drawn waits for the user's next message".

## Today

A local picture takes minutes, and an edit 657 to 962 seconds on a processor ([studio](../../architecture/studio.md#editing-a-picture)). `surfsense_make_image` answers `Queued` after 150 seconds, and a render naming that picture is refused while it is drawing ([`script_documents/service.py`](../../../surfsense_local/backend/modules/artifacts/script_documents/service.py)), so the agent can only tell the user to ask again.

## Design

- **The render is accepted.** `surfsense_render_document` with a picture name still being drawn creates the pending version as today, with `waits_for: [<artifact ids>]` in its metadata, and does not queue its job. The call answers at once: "Queued artifact <id>, version <n>: it renders once image-12 and image-14 are drawn. Do not render it again." The agent tells the user the PDF will appear in Studio.
- **A picture's job ending queues what waits on it.** At the end of every Studio job, where the worker already notifies the app ([`job.py`](../../../surfsense_local/backend/worker/studio/job.py)), it finds the pending renders in that picture's thread whose `waits_for` names it. Each one whose pictures have all ended is queued then, through `queue_job` as every version is ([`queued_job.py`](../../../surfsense_local/backend/modules/artifacts/queued_job.py)).
- **A picture that failed or was cancelled** fails the waiting render with a sentence naming it: "image-14 failed, so this PDF was not made. Draw that page again, or render without it." That failure counts under renders' three-failure limit when the next render is asked for, as a queued render's late failure does today ([`failed_renders.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/failed_renders.py)).
- **Only drawn pictures wait.** A source's figure or a chat's chart is there or not, so a missing one is refused as today. A web page saved with `surfsense_save_page` still refuses a picture being drawn, since a page is checked and screenshotted as it is saved.
- **A restart** settles waiting renders when the worker starts, beside the interrupted documents ([`interrupted_documents.py`](../../../surfsense_local/backend/worker/interrupted_documents.py)): one whose pictures have all ended is queued, one still waiting stays pending, and one waiting on a picture that was itself interrupted fails with the same sentence.
- **Cancel** in Studio works as on any pending version.
- **No one checks the previews** of a render that finishes after its turn. The comic's PDF is a fixed layout, one full-bleed picture a page, so little can go wrong, and the open thread links the PDF once it is ready, as it does for any queued version ([agent](../../architecture/agent.md#pictures-the-agent-makes)).

## Decisions

- **On the server, not in the agent.** A tool that polls, or a turn kept open, holds a call past its limit or a chat open for an hour; ADR 0087 rules out both. A pending version that the last picture's job queues needs no new process, no polling and no model awake.
- **In the job's end, not a timer.** The job that ends is the one event that can make a render ready, so nothing runs in between.

## Checks

- A render naming a picture still drawing answers `Queued` and is not queued; it renders once the picture is ready.
- One of two pictures ending leaves it waiting; the second queues it.
- A failed or a cancelled picture fails it, with the sentence, and the failure counts toward the next render.
- A worker restart queues it, keeps it, or fails it, as above.
- A web page naming a picture still drawing is still refused.
