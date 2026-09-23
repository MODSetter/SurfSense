# The model catalog

> **Being redesigned.** The [model catalog proposal](../../proposals/model-catalog.md) replaces this catalog: the curated manifest, the install gate, and the separate image model list. This page describes the code as it is until that work ships.

The model screen offers local generation models from two tiers: a curated
manifest of pinned builds (none yet marked `validated`), shipped frozen and priced offline from
committed header fields, and a search over every GGUF repo on Hugging Face,
which needs the network and is absent when egress is off. Every installable
build is badged by the same fit estimate ([`fit.md`](fit.md)). Curated models
are ordered by their position in the manifest, which picks the recommendation and
is never sent to the renderer, and installs key on an opaque id the server mints,
so the renderer can never name a download.

**Code:** [`surfsense_local/backend/modules/llm/catalog/`](../../../surfsense_local/backend/modules/llm/catalog/), [`surfsense_local/backend/scripts/refresh_curated_models.py`](../../../surfsense_local/backend/scripts/refresh_curated_models.py), [`surfsense_local/backend/scripts/curated/`](../../../surfsense_local/backend/scripts/curated/), [`surfsense_local/frontend/src/features/model-catalog/`](../../../surfsense_local/frontend/src/features/model-catalog/)
**Decisions:** [ADR 0014](../../adr/0014-two-tier-model-catalog.md), [ADR 0017](../../adr/0017-egress-off-by-default.md)

## Two tiers

| | Curated | Search |
|---|---|---|
| Source | `curated-models.json`, shipped frozen | `huggingface.co` |
| Network | none | required, egress gated |
| Priced from | committed `shape`, on first paint | the candidate build's header, when a repo is opened |
| Ordered by | manifest list position, never displayed | no order |
| Can be recommended | yes | no |

Two endpoints, deliberately. Curated plus installed renders offline and instantly
from `GET /llm/catalog`; search is its own request, returning at most 50 hits, so the screen never
waits on `huggingface.co`. One response covering both would either block on the
network or return partial results behind a flag.

## The manifest, schema 4

`curated-models.json` is source, not build output. A person runs the authoring
script, reads what it proposes, and commits the result. Reordering the ladder
shows up in a pull request where someone notices, a tag rebuilds to the same
manifest forever, and the cadence is honest: entries change when someone adds a
model, not when someone cuts a release.

```jsonc
{
  "model_id": "Qwen/Qwen3-8B",
  "family": "Qwen3",
  "label": "Qwen3 8B",
  "parameter_count": "8B",

  // DERIVED, per model. The script writes all of it.
  "shape": {
    "architecture": "qwen3", "block_count": 36,
    "head_count_kv": 8, "key_length": 128, "value_length": 128,
    "context_length": 40960, "n_vocab": 151936,
    "embedding_length": 4096, "feed_forward_length": 12288
    // ...the other ModelShape fields, zero or empty for a dense model
  },
  "capabilities": [],       // user facing only: "vision" or nothing
  "decode_fraction": 1.0,   // 1.0 dense; the active slice for a mixture of experts

  "variants": [
    {
      // DERIVED
      "repo": "unsloth/Qwen3-8B-GGUF",
      "file": "Qwen3-8B-Q4_K_M.gguf",
      "quantization": "Q4_K_M",
      "size_bytes": 5027784512,
      "mmproj": null,

      // JUDGEMENT, decided by a person beside the build it judges
      "validated": false
    }
  ]
}
```

The split is the point. Everything derived comes free from the GGUF header and
the Hugging Face listing; the judgement is one field a person sets for the build,
`validated`, plus the model's position in the list. That keeps the manifest
maintainable at twenty entries instead of six. There is no quality score anywhere
in the file.

- **`shape` is what makes the curated tier work offline.** Pricing a model means
  reading its header, and a curated entry is not downloaded yet, so without these
  fields an airgapped machine would have no fit badge on the one tier it can use.
- **`embedding_length` and `feed_forward_length` are required**, unlike their
  optional counterparts on `ModelShape`. A committed entry was authored by a
  script that read a real header, so a missing width means an entry written by
  hand or by an older script, and the compute buffer would price it as though the
  model had no layers to compute.
- **`validated` lives on the variant**, because it is a fact about one exact
  file: a person ran this build, not some other quantization of the model.
- **`variants` is a list** with one entry per model today, so a second build is a
  manifest edit, where changing the shape later would mean a schema bump and
  re-authoring every entry.

`validate_manifest` rejects a wrong `schema_version`, a duplicate `model_id` and
a duplicate `(repo, file)` pin. A manifest that fails validation,
including one missing a width, is replaced at startup by an empty one, so
installed models keep working.

The shipped six, all Qwen3 from `unsloth/*-GGUF`, all `Q4_K_M`, none validated,
listed smallest to largest:

| Model | File size |
|---|---|
| Qwen3 0.6B | 396,705,472 B |
| Qwen3 1.7B | 1,107,409,472 B |
| Qwen3 4B | 2,497,281,312 B |
| Qwen3 8B | 5,027,784,512 B |
| Qwen3 14B | 9,001,753,984 B |
| Qwen3 32B | 19,762,150,048 B |

## Authoring

`scripts/refresh_curated_models.py` in `surfsense_local/backend/`, run by hand. It
is not shipped, not in CI and not on any request path. Two tables are
hand-authored. `ENTRIES` holds six short fields per model (`model_id`, family,
label, parameter count, repo and quantization), none of which needs a download,
and each entry's position, which is the catalog's only preference signal.
`VALIDATED` names the files somebody has downloaded, chatted with and confirmed
citations resolve on; it is empty today. Everything else is read from the real file, never typed:

- `scripts/curated/huggingface.py` resolves a repo and quantization to one file,
  preferring the shortest name (`Qwen3-8B-Q4_K_M` over `Qwen3-8B-UD-Q4_K_M`) and
  excluding split parts, projectors and draft models, then reads its header over
  HTTP range without downloading weights.
- `scripts/curated/projector.py` finds an `mmproj` sibling, preferring F16, then
  BF16, F32 and Q8_0. A projector's presence is what sets `capabilities` to
  `["vision"]` and names `mmproj`.
- `scripts/curated/tensor_bytes.py` computes `decode_fraction`.

The script validates the result against the schema before writing it, so it fails
there rather than shipping something the app would reject.

`decode_fraction` is the share of a build's bytes read per decoded token:

```text
decode_fraction = (non_expert_bytes + expert_bytes × used / experts) / total_bytes
```

Sizes come from llama.cpp's `GGML_QUANT_SIZES` and the expert tensor set from its
`TENSOR_NAMES`, the seven members its own fitter matches and deliberately not
`ffn_norm_exps`, so a rename upstream is an import error rather than a pattern that
stops matching. Every shipped entry is dense and carries 1.0; it is computed anyway
because it is free from the header. Nothing reads it yet: the speed tiers use
only the offload fraction.

A refresh is due, realistically four or five times a year, when a model worth
recommending ships, a quantizer deletes or re-uploads a pinned file, the pinned
llama.cpp build is bumped and the pins want reverifying, a hardware class turns
out under-served, or someone reports a bad recommendation.

## Ordering

There is no score. A model's position in `ENTRIES`, and so in the manifest's
`models` list, orders the curated rows and selects the recommendation, and does
nothing else. It is never displayed, never compared outside the app, and never
applied to a searched model. The ladder runs smallest first and most preferred
last, so preferring a later entry reads as preferring the bigger model. Moving a
model is a one-line reorder, with no second field to keep in step with it.

The order means good at this app's job: answering from the user's documents with
citations that resolve, not general capability. That is why a person sets it
rather than a general-capability benchmark.

It can be set once because nothing about a pinned file changes with the machine.
Sweeping a general-capability scorer's device budget for Qwen3 8B, with host
memory held fixed, its quality figure moved only with the quantization it
landed on, and across 2,424 models none varied at a fixed quantization. A
preference over pinned files is therefore authoring-time data, shipped frozen
and never scanned or recomputed on the user's machine.

Staleness is acceptable by design. Airgapped means no refresh path, so a shipped
list ages, which would be fatal if curated were the only way to get a model; with
204,797 models one search away, curated ages into a starting point tested a while
ago rather than a boundary.

## Search

### Listing

```text
GET /api/models?filter=gguf&search=<q>&sort=downloads&direction=-1&limit=<=50&full=true
GET /api/models/{repo}/tree/main?recursive=true
GET /api/models/{repo}?expand[]=gguf&expand[]=pipeline_tag
```

Sorted by downloads, the only sort usable as a default. `likes` and
`trendingScore` surface uncensored derivatives in the top few, and `lastModified`
and `createdAt` surface half-finished uploads. Every order surfaces abliterated
fine-tunes somewhere near the top, which is what an open catalog means and not a
reason to reintroduce grading. The count is shown as popularity, never as
endorsement.

A hit is described, not judged: downloads, likes, licence, whether it is gated,
last modified, and provenance. 32 of the top 40 GGUF repos carry a
`base_model:quantized:<repo>` tag, so a row can say what the file was quantized
from, a fact rather than a grade. The screen searches once a query has two
characters and keeps results for 300 s, because Hugging Face allows 500 requests
per 5 minutes.

### Opening a repo

`GET /llm/search/{repo}` is where pricing happens, so the trigger is opening a
result, not hovering or typing.

1. `list_builds()` lists every single-file GGUF with its exact size, smallest
   first, dropping split sets (`-of-`), projectors (`mmproj`) and draft models
   (`draft`), none of which a user installs on its own. It is a display filter and
   decides nothing. The quantization comes from the filename with a regex tight
   enough to need a real quant token, because matching loosely reads `Qwen3` out
   of `Qwen3-Coder-30B-A3B-Instruct-UD-TQ1_0.gguf`, seen live; the last match
   wins.
2. `read_repo_facts()` asks Hugging Face for the repo's pipeline tag and whether
   its GGUF carries a chat template. It is never asked what the model is: Hugging
   Face parses one file per repo and serves that as the repo's answer, so a chat
   model shipped beside an `mmproj` sidecar came back as `clip`. That refused 17
   of the 1000 most downloaded repos, 13 of them vision models, each told to
   install the model it belonged to when that model was the repo itself.
3. `_candidate()` reads builds' own headers over HTTP range, at most four, until
   one is a model the denylist allows. `list_builds` orders by size and a draft
   head is always smaller than the model it accelerates, so judging the first
   file would reproduce the same failure from the app's own ordering. Normally
   this is one read.
4. The candidate's architecture and the repo's tag go through the install gate.
   The API still lists a refused repo's builds at their real sizes, badged
   `Cannot run` with the reason and not installable; the screen shows only the
   reason.
5. Otherwise every build is priced from the candidate's shape, at the cache
   precision the loader would choose, and gets an install ticket.

A repo with no chat template is installable and warns that it may answer badly
in a chat; that is a warning, not a fit state. A header that cannot be read does
not lose the repo: the builds fall back to a size-only shape, so every
architecture-derived term is zero and `need` is the file size plus the fallback
compute line, and the rows are marked approximate. Refusing the whole repo over
one unreadable header would hide builds the user can run.

### What a file is

`gguf/file_kind.py` reads what a GGUF is from official keys only: `general.type`
against `gguf.constants.GGUFType` (a model, `mmproj`, an adapter, an imatrix) and
`split.count` for shards, with `clip` as the architecture older projector writers
used. A header that parses and names no architecture is `NOT_LOADABLE`, because
`general.architecture` is what llama.cpp's loader dispatches on. Everything else
fails open, so a short read, a failed request and an unparseable file all count
as a model: a refusal made from a failure to read is the one mistake this tier
cannot afford. Refusing is also the cheap path. A projector, an imatrix or a
diffusion GGUF carries no tokenizer, so its metadata ends inside the 256 KiB probe,
while a chat model's `tokenizer.ggml.tokens` runs to megabytes (5.93 MB for
Qwen3 0.6B, 7.82 MB for Llama 3.2 1B) and truncates there: a header that does not
fit belongs to a real model. `reprice()` uses the same check to keep anything but
a model out of the preset ([`runtime.md`](runtime.md)).

### The install gate

`catalog/search/not_chat.py` is one denylist of 88 names, grouped by what a model
is (embedding, speech out, speech in, labellers, OCR, draft heads, projectors,
and other runtimes such as diffusion and video) with one sentence per group.
GGUF architectures and Hugging Face pipeline tags share the table, because they
answer the same question and their names never collide. `refusal(architecture,
pipeline_tag)` looks up both and returns the sentence a person reads, or nothing.

A denylist rather than an allowlist, because the two age in opposite directions.
An incomplete allowlist refuses a model that works and nobody finds out, because
the user is told no and believes it; an incomplete denylist admits a model that
does not work, which announces itself. llama.cpp adds architectures faster than
any list is updated, so the default has to be yes. The allowlist this replaced
refused 43 architectures the runtime supports, including Gemma 4, Qwen 3.5 and
Mistral 3, admitted `bert`, `nomic-bert`, `t5encoder` and others that abort the
worker on the first message, and carried three misspellings, such as
`granite-moe` for `granitemoe`, that had never matched anything.

The tag is there because a header can be honest and still mislead. Across the
1000 most downloaded GGUF repos, an embedding model declares `mistral3`, a voice
model and a reranker both declare `qwen3`, and a video encoder declares `qwen35`;
refusing those architectures would refuse Mistral and Qwen, so only the repo's
tag separates them. It is a denylist, not a tag requirement: about 43,500 of
204,797 GGUF repos carry a pipeline tag, so requiring one would hide four fifths
of the catalog. The tags that mean chat must never be added: `text-generation`,
`image-text-to-text`, `video-text-to-text`, `audio-text-to-text` and
`any-to-any`. `image-text-to-text` alone is 28% of admitted repos.

What it costs, measured over the same 1000 repos: 18 of 979 install and then
fail, all brand-new chat architectures that no denylist can name in advance. A
chat with one gets `MODEL_CANNOT_RUN`, "SurfSense cannot run this model. Pick
another model." `scripts/audit_gate.py` keeps the list honest: it runs the gate
over the top N repos and prints every refusal for review and every entry that
matched nothing, which is what a typo looks like. It needs the network, so it is
not part of the test suite; run it after a llama.cpp pin bump.

## Install ids

`POST /llm/install` takes `{"catalog_id": "...", "select": true}` and nothing
else: no repo, file, URL, local path or quantization. Letting the renderer post a
repo and file would hand it the ability to name an arbitrary download, which is
the capability the install contract exists to withhold. So the server mints ids
for both tiers and hands back only the id.

- **Curated:** `secrets.token_urlsafe(18)`, minted once per process and keyed on
  `(repo, file)`, opaque so the renderer cannot assemble one.
- **Searched:** an `InstallTicket`, minted when a repo is priced and held in
  memory for 300 s, the same window the screen's search cache uses. A ticket
  outliving its row would let a stale screen install something the user is no
  longer looking at.

`resolve_install()` checks curated ids first and then tickets, and the route
cannot tell them apart. Both failure modes return the same
`422 catalog id is stale or unknown; refresh the catalog`.

## List order and the recommendation

Curated rows sort by fit state, then manifest position with later entries
first, then `model_id`: fit coarsely, position finely. Sorting by position alone
would put a refused 32B at the top of a small machine's screen, which is the one
thing a model chooser must not do. A model with several builds is one row, taking
the best state among them, with a tie going to the build listed first in
`variants`, and installing the build that produced it, because the screen's job is
choosing a model. No row carries a position or a score: `CatalogRow` has no field
for one and the router serialises none, which is the surest way to keep the order
undisplayed.

`recommend()` prices every curated build at the cache the loader would choose,
keeps the builds whose speed tier is in `RECOMMENDABLE_TIERS` (`FULL` or
`LIGHT_SPILL`), and returns the one furthest down the ladder, breaking a tie
toward the smaller file, or `None`.

- **The gate is on speed, not residency.** Residency is a mechanism and speed is
  the goal; they coincide on a large card and diverge on a small one. Measured on
  an RTX 3050, Qwen3 8B spills about a quarter of its bytes and the machine's
  owner runs it without noticeable lag, so a rule that starred only fully
  resident builds would ban a configuration that demonstrably works. Decode is
  bandwidth-bound, prefill degrades half as much, and this app is
  prefill-dominated ([`fit.md`](fit.md)).
- **`TOO_BIG` is never recommendable**, so physics and speed are judged by one
  classification rather than a state check plus a separate threshold.
- **`None` is an honest answer.** Every build physics does not refuse stays
  installable; it simply goes unstarred.
- **The policy ranges over builds, not models**, because a build is what the user
  installs. With one variant per entry the behaviour is
  identical, and a second build is a manifest edit rather than a rewrite of the
  module, its tests and every fixture.

On screen the recommendation is a mark on its curated row, labelled "Recommended
for this computer", not a separate section.

What each machine gets, computed from the shipped manifest in capacity mode.
Cells are the state, with the offload fraction for a `PARTIAL` build:

| Machine | Resident | Refusal | 0.6B | 1.7B | 4B | 8B | 14B | 32B | Star |
|---|---|---|---|---|---|---|---|---|---|
| M2 8 GB | 4198 MiB | 6144 MiB | fits | fits | fits | 0.33 | too big | too big | 4B |
| RTX 3050 6 GB | 4210 MiB | 34046 MiB | fits | fits | fits | 0.33 | 0.60 | 0.81 | 4B |
| M4 16 GB | 9898 MiB | 14336 MiB | fits | fits | fits | fits | fits | too big | 14B |
| RTX 4070 12 GB | 9976 MiB | 40696 MiB | fits | fits | fits | fits | fits | 0.55 | 14B |
| RTX 4090 24 GB | 21976 MiB | 85464 MiB | fits | fits | fits | fits | fits | fits | 32B |
| M4 Max 64 GB | 48128 MiB | 63488 MiB | fits | fits | fits | fits | fits | fits | 32B |
| No GPU 16 GB | 14336 MiB | 14336 MiB | fits | fits | fits | fits | fits | too big | 14B |

Every machine gets a star, including the one with no GPU. The 3050's 8B is 0.33
by layers, `MODERATE_SPILL`, so that machine is starred the 4B although its owner
runs the 8B happily; the open measurement is in [`fit.md`](fit.md). The table
also shows what the manifest lacks, all manifest work rather than estimator work:
24 GB and 64 GB machines, 2.7× apart, get the same file, and a mixture of experts
is the right shape for them, which is why `decode_fraction` ships; a second
variant such as `Q6_K` on 8B and 32B would fill the 16 GB band; and all six
entries are text-only in an app that ingests PDFs and images.

## HTTP routes

All under `/llm`. The catalog routes are in `catalog/router.py`; delete lives in
`modules/llm/router.py` beside the selection routes ([`selection.md`](selection.md)).

| Route | Returns | Network |
|---|---|---|
| `GET /llm/system` | budget, devices, `gpu_status` | none |
| `GET /llm/catalog` | budget, `gpu_status`, curated rows, installed rows, `recommended_model_id` | none |
| `GET /llm/search?q=&limit=` | repos, described not judged | `huggingface.co`, egress `host:huggingface.co` |
| `GET /llm/search/{repo:path}` | builds with exact sizes and badges | `huggingface.co`, egress `host:huggingface.co` |
| `POST /llm/install` | NDJSON progress stream | `huggingface.co`, egress `host:huggingface.co` |
| `DELETE /llm/models/{model_name:path}` | `ModelDeleteRead`, with `selection_cleared` | none |

Search, repo reads and downloads are errands to one host and share one consent,
`host:huggingface.co`, which image model downloads use too
([`../egress.md`](../egress.md)). A destination that is off is a `403` with
`code: egress_disabled`; an unreachable host is a `503` naming `huggingface.co`.
With it off, search is absent rather than degraded: curated and installed rows
still render and are priced, and only installing needs the host. Local image
models have their own routes under `/llm/image/local` and their own runtime
([`../studio.md`](../studio.md)).

A curated row carries its opaque `catalog_id`, `model_id`, `variant_model_id`
(what the runtime calls the installed file, which Use and Delete act on), the
build's quantization and size, `fit`, `badge`, `capabilities`, `installed`,
`selected`, `can_install` and `recommended`. No response carries a quality score,
and none carries a `scanned` flag, because there is no scan.

## The install stream

NDJSON, one `{"type": …}` frame per line:

```text
starting     "Preparing download"
downloading  completed / total, repeated
verifying    "Checking the model"
preparing    "Preparing the model runtime"     preset rewritten, waiting for the router
preparing    "Loading the model", progress     the router loading it, repeated
selecting    "Selecting model"                 only when select is true
complete     "Model is ready"
             or "Downloaded. It becomes available once the runtime restarts."
error        "The model could not be installed. Retry the download."
```

The API fetches `https://huggingface.co/{repo}/resolve/main/{file}` into the
models directory itself: llama-server is a second process the app does not
proxy, so an in-process fetch is the only place `egress.require()` can hold. The
download writes a sibling `.part` file and renames it only once the whole file is
present, so the router never discovers a partial model. A cancelled download keeps
the `.part`, and the next attempt resumes with a `Range` request, discarding the
held bytes if the server answers without a `206`. One install runs at a time,
enforced by an `asyncio.Lock` and a `409`, because two downloads compete for the
same disk and the screen has one progress bar. After the download, `reprice()`
rewrites the preset and the stream waits for the router to list the model, then
asks the router to load it and forwards the router's own progress as `preparing`
frames carrying `progress` from 0 to 1. The router names each stage, so a vision
model says "Loading image support" for its projector rather than sitting at
100% ([`runtime.md`](runtime.md)).
Listed is not loaded: without the load, the install reported success and the
first question paid a cold load. With `select`, the model becomes the generation
selection before `complete`.

## On the screen

Onboarding and Settings share the model screen. From the top:

- **A hardware line**, on first paint, with no scan and no button: the graphics
  card and its memory, or the Apple Silicon GPU, or "Runs on your processor", or,
  for `broken_install`, that the runtime did not detect the graphics card and a
  reinstall fixes it.
- **Installed**: the files in the models directory, each with "Use", or "In use"
  when selected, and deletable after confirmation. For a model installed from
  search this list is the only place it appears, since it has no curated row.
- **Tested by SurfSense**: the curated rows, grouped by family. Each shows its
  label, fit badge and reason line, "Reads images" when the entry has the
  `vision` capability, the download size, and one action: "Download", "Use" for
  an installed model, or a disabled "In use".
- **All models**: the search. Focusing the box is what raises the egress question
  when `host:huggingface.co` is off, once per visit, so a refusal is not the
  user's first news that search is off. Each hit shows its downloads, licence,
  "Needs an account" when gated, and what it was quantized from; opening it reads
  the repo's builds, each with its badge and a "Download" button. The results
  area reserves its height, so the page does not jump as it moves from prompt to
  spinner to list.

Rules the screen holds:

- Reduced speed installs exactly like Full speed, with no confirmation: it runs,
  slower, and llama.cpp places the layers. Only Won't fit blocks, and its reason
  line states the required and available sizes. The star can sit on a Reduced
  speed row, and the manifest order is never displayed.
- While installing, the row's button names the phase ("Downloading",
  "Preparing") and the row shows the current step, bytes, percent and a Cancel
  button. Each phase starts its own bar rather than animating down from the last,
  and a phase with no figure holds an empty bar instead of an invented one.
  Progress is announced through a throttled live region, and the other model
  actions are disabled. A cancelled install says so and stays retryable; a
  finished one refreshes the catalog and selection queries.
- Use on an installed model calls `PUT /llm/selection/text_gen` with the
  runtime's name for the file, which also starts loading it
  ([`selection.md`](selection.md)).
- Delete calls the backend; the renderer never touches the models directory. The
  backend refuses with a `409` while an install runs, while Studio is generating,
  or while the model is answering a chat, and deleting the selected model clears
  the selection without choosing another.
- When search is off or unreachable, the search section says so and the rest of
  the screen is unaffected.

## How it is tested

Unit tests in
[`surfsense_local/backend/tests/unit/llm/catalog/`](../../../surfsense_local/backend/tests/unit/llm/catalog/)
cover the manifest, rows, the recommendation, reprice, the gate and search
against mocked transports; the routes are covered in
[`surfsense_local/backend/tests/integration/llm/`](../../../surfsense_local/backend/tests/integration/llm/),
and the screen in `model-catalog.test.tsx`.

## Known gaps

- Adding a `.gguf` from disk has no screen; only the empty-state copy mentions it. A file copied into the models directory by hand is picked up at the next start, when `reprice()` writes its preset ([`runtime.md`](runtime.md)).
- A vision model installs as text only: `InstallPlan` carries one file (`model_id, repo, file, size_bytes`) and install fetches one file, so the projector is never downloaded, and search pricing calls `estimate()` without `mmproj_bytes`.
- Downloads are not checksum-verified: `download_gguf()` accepts a `sha256`, but the manifest has no field for one and `install()` passes none, so the `verifying` frame checks nothing.
- The API does not cache search: `CACHE_SECONDS` is declared and unused, so only the renderer's 300 s query cache stands between typing and Hugging Face's rate limit.
- Search hits carry no fit badge; only the builds of an opened repo are priced.
- A dead curated pin, a 404 at download, gets the generic install error; nothing says the model is gone from its source or falls through to the next-best entry.
- The screen never marks the runtime unavailable, so installs stay enabled while llama-server is down.
- A Won't fit row states the sizes but does not name a smaller build.
- Nothing checks free disk space before a download starts.
- Curated rows send `context_length: 0` and no architecture, so cards show neither.
