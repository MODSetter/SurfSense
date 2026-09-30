---
status: deferred
code:
  - surfsense_local/backend/modules/embedding/
  - surfsense_local/backend/worker/ingestion/
  - surfsense_local/frontend/src/features/settings/
---

# Changing the embedding model

> Future scope. After [choosing once](embedding-model-choice.md) ships, the user can change the embedding model in Settings. The library is re-embedded in the background into a second index while search keeps using the first, and one transaction switches them. Nothing is re-parsed or re-chunked, and every citation keeps working.

Deferred by product decision: the index is fixed at onboarding until this ships. Everything it needs is laid down by [choosing once](embedding-model-choice.md), so this adds code and changes no schema.

## What it builds on

| From choosing once | Used here as |
|---|---|
| `embedding_indexes` rows with a spec snapshot and a `state` | a second row, `building`, is how a change starts |
| the vector table named in the row | the new index gets its own table beside the old one |
| `documents.embedding_index_id` | which documents the new index has done |
| the chunker's own pinned tokenizer | chunks stay put, so chunk ids and citations survive |
| `write_vectors()` looping over live indexes | new uploads land in both indexes during the change |
| `embed_chunks(index, chunk_ids)` | the re-embed job is this, in batches |
| `active_index()` on the read path | search follows the switch with no change |
| `GET /embedding/index` → `{active, building}` | `building` carries progress |
| bge bundled | switching back to bge never needs a download |
| the delete guards on the active model and its connection | lifted from the old index at the switch, so its model and connection become deletable |

## The change

1. **Pick.** Settings › Embedding model gets a Change button. It resolves and downloads the new model exactly as onboarding does.
2. **Start.** One transaction inserts an `embedding_indexes` row with `state = building` and creates its vector table at the new width.
3. **Fill.** A job on the ingest queue ([ADR 0008](../adr/0008-two-job-queues.md)) runs `embed_chunks` over the documents not yet stamped with the new index, in batches, reading chunk text from `chunks`. A document is stamped when all of its chunks are in.
4. **Keep up.** Uploads, notes, Studio artifacts and imports during the change write to both indexes through `write_vectors()`.
5. **Switch.** When every document is stamped, one transaction sets the new row `active` and the old one `retired`. Search reads the active row, so the next question uses the new model.
6. **Clean up.** The retired index's vector table is dropped. Its model becomes deletable, unless it is bge, and so does the connection it called.

Search serves the old index, and embeds questions with the old model, until step 5. There is no moment where a question is compared against vectors from another model.

## Interruptions

- **App closed mid-change.** The job resumes at the next launch from the stamps; a document half done is redone.
- **Cancel.** Deletes the `building` row and drops its table. The active index was never touched.
- **A second change while one is running.** Refused: the running change is cancelled first. One `building` row at most.
- **Ingest failure on one document.** It stays unstamped and is retried; the switch waits for it, and Settings names it.

## Settings while it runs

The section shows the old model as in use, the new one as building, progress as documents done of total, and Cancel. Chat and search work throughout on the old model.

## Cost

- Time: bge measured at about 8 minutes per 1,000 passages on a mid CPU ([retrieval](retrieval.md)); a larger model is slower.
- Disk: both vector tables exist until the switch, so vector storage roughly doubles for the length of the change.
- Memory: the ingest worker holds both models while new uploads write to both indexes.
- Money: a change to a remote model is billed for every passage in the library, and uploads during the change embed twice.

## What this makes recoverable

[Choosing once](embedding-model-choice.md) offers Hugging Face and remote models at onboarding and accepts that some failures have no repair. This is the repair:

| Failure | Until this ships | With this |
|---|---|---|
| a Hugging Face pick ranks badly | stays | change to a measured model |
| a Hugging Face repo is deleted and the local copy is lost | search stops for good | change to any other model |
| a remote provider retires the model | search stops for good | change, ideally before, when Settings shows the deprecation warning |
| the user no longer wants documents sent to a host | turn the host off and lose search | change to a local model, then turn it off |

A change never needs the old model: the re-embed reads chunk text, not the old vectors, so it works even when the old provider or repo is already gone. What is lost in that case is search while the change runs, because the old index can no longer embed a question.

## A smaller first cut

A **blocking rebuild** covers every row of that table with less machinery: search is paused, a new index row is created, `embed_chunks` re-embeds every chunk into it, and it becomes active. No `building` state serving beside the old index, no dual writes, no progress beside a working search. It is the fastest way to close the no-repair cases [choosing once](embedding-model-choice.md) accepts, and the background change above replaces it later without a schema change.

## Open questions

These come from [retrieval](retrieval.md), whose migration section this replaces.

- Does a change start on its own after an app update ships a better default, or only when the user asks? A library of any size makes this a long, visible job.
- Is the switch automatic when the job finishes, or does the user confirm it?
- Should the retired index be kept for a while as an undo, at the cost of its disk?
- Does the blocking rebuild ship first, or go straight to the background change?
