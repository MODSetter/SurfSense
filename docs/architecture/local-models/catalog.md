# The local model catalog

> **Partly built.** This page describes the local catalog as the code stands. The [model catalog proposal](../../proposals/model-catalog.md) is in progress: the one screen with Source and Capability filters and searched image models are still to come, and this page moves to `model-catalog/local.md` when that work ships.

The model screen offers local models from three origins, all as one row shape:
curated models from a packaged manifest of pinned builds, priced offline; files
already in the models folder, judged from their own headers; and a search over
every GGUF repo on Hugging Face, which needs the network and is absent when
egress is off. Every build is priced by the same fit estimate ([`fit.md`](fit.md)).
Only curated models are ever recommended, as a model or as a build. Installs key
on an opaque id the server mints, so the renderer can never name a download.

**Code:** [`surfsense_local/backend/modules/llm/catalog/local/`](../../../surfsense_local/backend/modules/llm/catalog/local/), [`surfsense_local/backend/modules/llm/providers/llamacpp/download.py`](../../../surfsense_local/backend/modules/llm/providers/llamacpp/download.py), [`surfsense_local/backend/scripts/refresh_local_manifest.py`](../../../surfsense_local/backend/scripts/refresh_local_manifest.py), [`surfsense_local/backend/scripts/local_manifest/`](../../../surfsense_local/backend/scripts/local_manifest/), [`surfsense_local/frontend/src/features/models/local/`](../../../surfsense_local/frontend/src/features/models/local/)
**Decisions:** [ADR 0014](../../adr/0014-two-tier-model-catalog.md), [ADR 0017](../../adr/0017-egress-off-by-default.md), [ADR 0026](../../adr/0026-curated-order-is-list-position.md), [ADR 0027](../../adr/0027-egress-consent-per-host.md)

## Three origins, one row

| | Curated | Downloaded | Search |
|---|---|---|---|
| Source | `manifest/models.json`, packaged | the models folder | `huggingface.co` |
| Network | none | none | required, egress gated |
| Priced from | committed `shape`, exact | the file's header, exact | file sizes, an estimate |
| Type and support from | committed `evidence` and GGUF keys | the file's header | the repo's tag and file names, then the header at install |
| Default and recommended build | yes | no | no |
| Can be starred | yes | no | no |

Every row is a `LocalRow` ([`rows.py`](../../../surfsense_local/backend/modules/llm/catalog/local/rows.py)):
its types, to which the route adds `selectable_for` ([`selection.md`](selection.md)), its support
(`context`, `reads_images`, `tools`, `reasoning`), whether the bundled runtime can
run it and why not, the `engine` that offered it, its builds, the build it leads
with and why, and the star. Each build is a set of files with roles, and carries
its fit, badge, whether it is installed, whether it is recommended, and whether it
reads images. An image build's `fit` and `badge` are `null`: sd.cpp has no fit
estimate, so the row states the download size and nothing about this machine,
and nothing blocks its install. The screen renders these fields and computes none
of them.

`GET /llm/catalog/local` returns llama.cpp's rows and then sd.cpp's, the three
curated image models, only when Electron handed the API an images folder, which
it does when it staged sd-server.

## One slice per engine

Only what every engine shares lives at `catalog/local/`. Each engine is a slice
under [`engines/`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/), with its sub-parts grouped into folders:

```text
catalog/local/
  build.py  listed_file.py  quantization.py  classifier.py  installs.py  rows.py
  manifest/                 the entry envelope, strict config, loader, models.json
  install/                  plan.py, download.py (one path for every engine), tickets.py
  engines/
    engine.py               the seam: what every engine answers
    registry.py             which engine runs which type, and the entry fields each reads
    llamacpp/               engine.py, manifest_fields.py, support.py, pricing.py,
                            builds/, rows/, models_folder/, search/
    sdcpp/                  engine.py, manifest_fields.py, evidence.py,
                            builds/, rows/, images_folder/
  service.py  router.py  schemas.py  dependencies.py
```

[`engine.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/engine.py) is the one seam the service and the routes
speak to. Each engine answers where its files land (`folder`), its rows,
whether it `holds` an installed model, the `check` before a download, the steps
`after_install` (llama.cpp rewrites the preset, waits for the router and warms
the model; sd.cpp has nothing to do, since sd-server takes its model at launch),
what to settle `after_remove`, and what to do `on_startup` (llama.cpp writes the
preset; sd.cpp records legacy downloads). The selection an install fills is the
engine's `model_type` and `provider`.

| | [`engines/llamacpp/`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/) | [`engines/sdcpp/`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/) |
|---|---|---|
| Evidence | GGUF metadata keys | tensor names (`evidence.py`) |
| Manifest fields | `context` (required), `shape`, `template`, `sampling` | `image` defaults (required) |
| Which files make a build | every build a repo offers, each with the repo's projector (`builds/in_repo.py`) | every GGUF at the repo's root, alone (`builds/in_repo.py`) |
| Default build | the first in a preference order led by `UD-Q4_K_XL` (`builds/choice/`) | `Q4_0`, the only build pinned (`builds/choice.py`) |
| Its folder | `models_folder/`: the scan, the preset, readiness | `images_folder/`: its files, legacy downloads, the installed image |
| Also | support, pricing, the recommended build, the lead build, the star, search | |

A slice holds what the catalog knows about a runtime. Running it stays outside
`catalog/`: the clients in `providers/`, and `fit/`, which prices llama.cpp.

## The manifest

`catalog/local/manifest/models.json` is source, not build output: a script
writes it, a person reads the diff in a pull request, and packaging bundles the
committed file. Position in `models` is the only preference signal, most
preferred first, and nothing in it is a score.

```jsonc
{
  "schema_version": 1,
  "refreshed_at": "2026-09-23",
  "models": [
    {
      "id": "qwen3-8b", "name": "Qwen3 8B", "family": "Qwen3", "publisher": "Qwen",
      "description": "…", "license": "apache-2.0", "source_repo": "Qwen/Qwen3-8B",
      "aliases": ["Qwen/Qwen3-8B", "Qwen/Qwen3-8B-GGUF", "bartowski/Qwen_Qwen3-8B-GGUF"],
      "evidence": { "architecture": "qwen3", "pipeline_tag": "text-generation", "parameters_b": 8.19 },
      "context": 40960,
      "template": { "tools": true, "reasoning": true, "system_role": true },
      "sampling": { "origin": "unsloth/Qwen3-8B-GGUF@a6adef13…/params", "thinking": { … } },
      "image": null,
      "shape": { "block_count": 36, "head_count_kv": 8, … },
      "builds": [                                    // smallest first; order carries no preference
        {
          "quantization": "UD-Q4_K_XL",
          "files": [
            { "role": "weights", "repo": "unsloth/Qwen3-8B-GGUF", "upstream_repo": null,
              "revision": "a6adef13…", "path": "Qwen3-8B-UD-Q4_K_XL.gguf",
              "size_bytes": 5135…, "sha256": "…" }
            // a vision build adds { "role": "projector", …, "gguf": { "clip.has_vision_encoder": true, … } }
          ],
          "run": { "args": [] },
          "validated": { "llama_cpp": null }
        }
      ]
    }
  ]
}
```

- **Every file is pinned** to a commit and a sha256, so a quantizer renaming or
  re-uploading on `main` cannot change what is downloaded, and every download is
  verified.
- **Vision is a file, not a label.** A build that reads images lists its projector,
  with the projector's own GGUF keys under llama.cpp's names.
- **`parameters_b` is counted from the tensor table.** No size, parameter count
  or architecture is read from a filename. Names only sort files into builds
  ([below](#which-files-make-a-build)) and give the quantization label, which
  keeps a quantizer's prefix (`UD-Q4_K_XL`) because the preference order ranks it.
- **`shape` is optional** for a model the llama.cpp estimator does not price.
- **An entry carries its engine's fields and no others.** The classifier reads
  `evidence`, the registry names the engine, and the engine names the fields it
  reads and the ones it needs. A text model needs `context`; an image model
  needs `image` defaults and carries no `context`, `shape`, `template` or
  `sampling`, because sd.cpp reads none of them. A field no engine reads would be
  reviewed and trusted while doing nothing. `validated` records `llama_cpp` or
  `sd_cpp`, the runtime build a person ran the build on.
- **`aliases` fold a download into its curated row.** A downloaded file shows as
  a curated build when its install record names the model's `source_repo`, an
  alias or a build's repo with the same quantization, or, with no record, when
  its file name is the build's own.

The shipped ten, none validated, most preferred first within each type. Seven
chat models, all from `unsloth/*-GGUF` with 18 builds each: Qwen3 32B, 14B, 8B,
4B, Gemma 3 4B (reads images), Qwen3 1.7B and 0.6B. Three image models, one
self-contained `Q4_0` file each, the same files and hashes the hard-coded list
they replace downloaded: Stable Diffusion 1.5 and XL from `kostakoff/*-GGUF`,
and SDXL Turbo from `gpustack/stable-diffusion-xl-1.0-turbo-GGUF`, whose licence,
`sai-nc-community`, allows non-commercial use only without a Stability AI
membership. llama.cpp's catalog skips the image entries; sd.cpp's offers them. `LocalManifest` rejects a wrong version, a repeated id or
quantization, an unpinned or unhashed file, a build without weights or with two
projectors, an entry no bundled engine runs, and any field it does not declare. A manifest that fails is replaced
at startup by an empty one, so downloaded models and search still work.

## Authoring

`scripts/refresh_local_manifest.py`, run by hand; never in CI, at packaging or
on a request path. `local_manifest/entries.py` is the hand-authored input:
which models, in which order, from which repo; `VALIDATED`, one in each
engine's `refresh.py`, is the other. For each repo the script reads the
commit sha, the file listing at that commit (sizes and `lfs.oid` hashes) and the
repo's `params` file, then the default build's header and its projector's header
over HTTP range requests. No weights are downloaded. Each engine reads its own
entries: `local_manifest/llamacpp/` and `local_manifest/sdcpp/` each hold a
`refresh.py` (the network) and an `assemble.py` (pure, the written entry).

- **An image entry's evidence comes from its tensors**, the only thing an sd.cpp
  file states, and what a person reviews comes from the entry: the `image`
  defaults, each with the source it was read from, and sd-server's `run.args`.
  Only what the publisher's card or report states is filled; the rest is left to
  sd-server's defaults.
- **It pins every chat build in the quantization preference order**
  ([`build_choice/preference.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/builds/choice/preference.py)),
  and nothing outside it: no imatrix files, drafters, big endian builds, or
  quantizations such as `TQ1_0` that the order does not rank.
- **It refuses to write** a build without a hash or size, a projector that does not
  see images or is not as wide as the model, and a refresh that drops a model or
  a build, listing what would go, unless it is rerun with `--accept-loss`.
- **`VALIDATED`**, one in each engine's `refresh.py`, names builds somebody ran,
  with the runtime build they ran it on: a chat build downloaded, chatted with
  and its citations confirmed to resolve. Both are empty.

The script's assembly is tested over recorded input, with no network
([`test_local_manifest.py`](../../../surfsense_local/backend/tests/unit/scripts/test_local_manifest.py),
[`test_local_manifest_sdcpp.py`](../../../surfsense_local/backend/tests/unit/scripts/test_local_manifest_sdcpp.py)).

## Which files make a build

[`repo_builds.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/builds/in_repo.py)
turns a listing into builds, for the refresh script and for search alike, so a
curated repo and a searched one never disagree about which file is the model and
which is its projector:

- Imatrix files, drafters (`mtp`, `draft`, `dflash`, `eagle`, in a name or a
  folder) and big endian builds are not builds.
- A split build is every part, listed in order, or nothing when a part is missing.
- Weights at the root and in folders named after a quantization (`BF16/`) count;
  any other folder (`distilled/`) does not. The root wins a quantization both hold.
- `preferred_projector()` picks the repo's projector by name (F16, then BF16, F32,
  Q8_0) and every build carries it, so its bytes count toward the footprint.

## Which build a row shows

For each curated model, in [`build_choice/`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/builds/choice/):

1. **The default**, blind to hardware: the first build in the preference order,
   `UD-Q4_K_XL` for every shipped model.
2. **The recommended build** on this machine: the default when its speed tier is
   `FULL` or `LIGHT_SPILL`, else the largest smaller build that is, never one
   above the default and never one below four bits (`RECOMMENDABLE`). Else none.

[`lead_build.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/rows/lead_build.py)
then names the build each row leads with, which is what its Download fetches, and
why: `in_use`, then `installed`, then `recommended`, then `fits_slower` (the
largest four bit or better build that installs), then `nothing_fits` (the default,
when no build of four bits or more installs, to say how big the model is). A
searched row leads with nothing; it lists every build.

An image row, in sd.cpp's
[`lead_build.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/rows/lead_build.py),
leads with the build in use, then an installed one, then its default (`default`,
`Q4_0`). With no fit there is nothing to recommend or to fall back from. A build
is installed when the images folder's `installs.json` names its repo and
quantization, or when its own file is in the folder.

**The star** goes to the first curated model, in manifest order, with a
recommended build, so a machine short of the preferred model's default gets a
smaller build of it before a smaller model. Curated rows sort by the fit of the
build they lead with, then by manifest position: a refused 32B at the top of a
small machine's screen is the one thing a model chooser must not do.

## Badges

A badge is a warning, shown only when there is something to warn about
([`fit.md`](fit.md#badges)): nothing for a build that runs fully or spills a
little, "Reduced speed" in amber for a heavier spill, "Won't fit" in red. The
tiers a build can be recommended at are exactly the tiers with no badge, so a
recommended build never warns. A row can still show both: the star sits beside
the build the row leads with, which is the one in use or installed before the
recommended one. A light spill is described quietly in the reason line instead.

## What a model is, and whether it can run here

[`classifier.py`](../../../surfsense_local/backend/modules/llm/catalog/local/classifier.py)
turns an architecture and a pipeline tag into a type. It names what is not a chat
model and calls everything else `TEXT_GEN`, because llama.cpp gains
architectures faster than any list is updated: embedders, rerankers, speech
recognisers, labellers, OCR, drafters and projectors are known and typeless;
diffusion architectures are `IMAGE_GEN`, video `VIDEO_GEN`, text to speech
`AUDIO_GEN`. The tag only refuses or refines, never admits, and the tags that
mean chat are never keys. An unreadable header fails open to `TEXT_GEN`, marked
approximate. Each group keeps its own sentence, which becomes a row's reason for
not running here. A row is runnable when the engine that offered it is the one
the registry gives its type: sd.cpp's image rows run, while the same image model
found through llama.cpp's search does not, and keeps its sentence.

A diffusion GGUF from sd.cpp's converter carries no metadata at all, not even
`general.architecture`, so the sd.cpp slice reads its architecture from tensor
names, as sd.cpp does
([`engines/sdcpp/evidence.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/evidence.py)):
a second text encoder (`conditioner.embedders.1.`, or `cond_stage_model.1.` from the converter SDXL Turbo's file came from) is `sdxl`, an SD 1 text
encoder (`cond_stage_model.transformer.text_model.`) is `sd1`. Nothing reads it
yet at runtime; the refresh script writes it into each image entry's evidence.

## Vision

[`support.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/support.py)
reads image support from GGUF keys under llama.cpp's own names: a projector
(`general.type` is `mmproj`, or the older `clip` architecture) with
`clip.has_vision_encoder`, whose `clip.vision.projection_dim` matches the model's
`embedding_length`. A curated build answers from the keys the refresh committed; a
downloaded one from the projector file on disk; a searched one from the repo's
file names until its header is read at install. The screen says **Vision**, once
per row.

- **Pairing is recorded, never guessed.** An install writes `installs.json` in
  the models folder
  ([`installs.py`](../../../surfsense_local/backend/modules/llm/catalog/local/installs.py)),
  naming each model's weights and projector, and saves the projector as
  `mmproj-<model>.gguf` so two vision models never share or overwrite one. A file
  copied in by hand pairs under that name too. A projector merely sitting beside a
  model is never attached to it.
- **Both halves download, price and load together.** The footprint includes the
  projector, `estimate()` charges it, and the preset names it ([`runtime.md`](runtime.md)).
- **It says the model can see, not that chat will show it an image.** Chat sends
  text only.

## Search

```text
GET /api/models?filter=gguf&search=<q>&sort=downloads&direction=-1&limit=<=50&full=true
GET /api/models/{repo}?expand[]=sha&expand[]=pipeline_tag&expand[]=gated&expand[]=gguf
GET /api/models/{repo}/tree/main?recursive=true
```

Sorted by downloads, the only sort usable as a default; the count is popularity,
never endorsement. A hit is described, not judged: downloads, licence, whether it
is gated, and **Vision** when its file names include a projector, by the same rule
`repo_builds.py` uses. `full=true` returns every repo's file names, so this costs no
request of its own. Each hit also carries `quantized_from`, from its
`base_model:quantized:` tag, which the API returns and the row does not show. The
screen searches once a query has two characters and keeps results for 300 s.

**Opening a repo reads its listing and no file**, about a second: the summary and
the file tree, fetched together. Every build is listed smallest first with its
exact size and an estimated fit, whose badge is marked `~`, which over-charges
on purpose (the weights plus 15% and a gibibyte, in
[`pricing.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/pricing.py))
so it never calls a spill resident. The type comes from the repo's tag and
Hugging Face's parsed architecture, ignored when it names a projector, and is
marked approximate. An estimated fit never refuses, because the exact answer
comes before any bytes move. A repo whose type is not `TEXT_GEN` gets no install
ids, so none of its builds can be downloaded.

**Installing a searched build reads it exactly.**
[`exact_check.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/search/exact_check.py)
reads the weights' header and the projector's, and drops a projector that does
not see or belongs to another model. llama.cpp's engine then refuses a file that
is not a model, a type the runtime cannot run, or a build too big for the
machine, with the sentence a person reads. A header parses in about 50 ms, because a vocabulary is
counted rather than decoded
([`header_prefix.py`](../../../surfsense_local/backend/modules/llm/gguf/header_prefix.py)).

## Install ids

`POST /llm/install` takes `{"catalog_id": "...", "select": true}` and nothing
else: no repo, file, URL, path or quantization, so the renderer cannot name an
arbitrary download. A curated build's id is minted once per process and keyed on
its repo and weights path; a searched build's is a ticket holding the whole build
and the repo's tag, kept for 300 s, the window the screen's search cache uses.
Both fail the same way: `422 catalog id is stale or unknown; refresh the catalog`.

## The install stream

NDJSON, one `{"type": …}` frame per line:

```text
starting     "Checking the model"              every install; only a searched build's headers are read
error        the reason, and the stream ends   when the exact check refuses
starting     "Preparing download"
downloading  completed / total, repeated       across every file of the build
verifying    "Checking the model"              each file with a hash was checked as it landed
preparing    "Preparing the model runtime"     preset rewritten, waiting for the router
preparing    "Loading the model", progress     the router loading it, repeated; "Loading image
                                               support" or "Loading the draft model" for those stages
selecting    "Selecting model"                 only when select is true
complete     "Model is ready"
             or "Downloaded. It becomes available once the runtime restarts."
error        "The model could not be installed. Retry the download."
```

The API fetches each file of the build from
`https://huggingface.co/{repo}/resolve/{revision}/{path}` into the models folder
itself, verifying every file against its sha256 (a searched file whose listing
gives no LFS hash goes unchecked): an in-process fetch is the only place
`egress.require()` can hold. Each file lands as a `.part` and is renamed
only when whole and verified, a cancelled download resumes with a `Range`
request, and one install runs at a time. Then the install record is written,
`reprice()` rewrites the preset, the stream waits for the router to list the
model and forwards its load progress, and with `select` the model becomes the
`text_gen` selection ([`runtime.md`](runtime.md)).

An image build takes the same stream into the images folder, with its record in
that folder's `installs.json`. It skips both `preparing` phases: sd-server takes
its model at launch, from the selection, so there is no router to restart and
nothing to warm. With `select` it becomes the `image_gen` selection, and
Electron starts sd-server on it ([`../studio.md`](../studio.md)).

Deleting a model removes every file its install record names, every part of a
split build and its projector, and forgets it. A file with no record, one copied
in by hand, loses only `<id>.gguf` and `mmproj-<id>.gguf`. `DELETE /llm/models/{name}`
finds the name in either folder, and clears the `text_gen` or `image_gen`
selection that named it.

**Image models the hard-coded list downloaded** were saved as `sd15-q4_0.gguf`,
`sdxl-base-q4_0.gguf` and `sdxl-turbo-q4_0.gguf`, each verified against the
sha256 the manifest now pins. At startup `warm()` records each one as its curated
build ([`engines/sdcpp/legacy.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/images_folder/legacy.py)),
in place rather than renamed, since sd-server may hold it open, and revision
`0015` renames the selection that named it to the build's id.

## HTTP routes

All under `/llm`, in [`local/router.py`](../../../surfsense_local/backend/modules/llm/catalog/local/router.py);
delete is in `modules/llm/router.py` beside the selection routes.

| Route | Returns | Network |
|---|---|---|
| `GET /llm/system` | budget, devices, `gpu_status` | none |
| `GET /llm/catalog/local` | budget, `gpu_status`, every local row, `recommended_id` | none |
| `GET /llm/catalog/local/search?q=&limit=` | hits, described not judged | `host:huggingface.co` |
| `GET /llm/catalog/local/search/{repo:path}` | the repo's row: builds with exact sizes and estimated fit | `host:huggingface.co` |
| `POST /llm/install` | NDJSON progress stream | `host:huggingface.co` |
| `DELETE /llm/models/{model_name:path}` | `ModelDeleteRead`, with `selection_cleared` | none |

Search, repo reads and downloads share one consent, `host:huggingface.co`
([`../egress.md`](../egress.md)). A destination that is off is a `403` with
`code: egress_disabled`. An unreachable host is a `503` naming `huggingface.co`
on search and repo reads, and the stream's generic error during an install.

## On the screen

Settings has one section per model type, **Chat** and **Image** in the nav, each headed **Text generation models** / **Image generation models** on its own page.
Each names the model in use at the top, then groups the slot's models by source:
**This computer**, every build on disk, curated or not, with Use (when its type
can fill the slot) or In use and Delete after confirmation; then one group per
connected server ([`../connections.md`](../connections.md)). **Add model** opens
one page with both ways in, laid out alike, no card or border around either:
**Use a server**, collapsed to a Connect button until opened, because it is
short, then **On this computer**, the catalog below. Both sections read the
one `GET /llm/catalog/local`: chat takes every row but sd.cpp's, and image takes
only sd.cpp's, each curated model with its size and a Download. The catalog
carries sd.cpp's rows only when the API has an images folder, which Electron
hands it only when `sd-server` is staged, in dev or packaged
([`../packaging.md`](../packaging.md));
otherwise the image section's part of the page says image models cannot run on
this computer, and the layout stays the same.

The chat catalog, from the top:

- **A hardware line**, on first paint, with no scan and no button.
- **Tested by SurfSense**: the curated rows, grouped by family. Each shows the
  star when it is the one for this computer, its name, a badge only when it warns,
  **Vision** when it reads images, the build it leads with and its size, and one
  action. "N other builds" opens the rest, each with its badge, size and action.
- **All models**: the search, its own box because what the user types goes to a
  third party. Focusing it raises the egress question once per visit when
  `host:huggingface.co` is off. Results scroll inside their own capped-height
  list rather than lengthening the page, the same as a server's model list
  ([`../connections.md`](../connections.md)).

Rules the screen holds:

- The install button names the phase ("Starting…", "Downloading…",
  "Verifying…", "Preparing…", "Selecting…"), and the progress bar and Cancel sit under the build being
  installed, curated or searched. "Other builds" stays open while one of its
  builds installs.
- Reduced speed installs like any other build, with no confirmation. Only a
  refusal blocks.
- Install errors, including the exact check's refusals, show as a toast.
- An install belongs to the app, not the page that started it: leaving the
  Add model page or closing Settings does not cancel it, and the section's list
  shows its progress until it ends.
- The image section uses the same cards, install states and progress as chat;
  it only downloads without selecting, so a model is chosen with Use once it is
  on disk. Every downloaded model has Delete, the one in use included: the API
  clears the image slot, and Electron stops sd-server on its next poll.

## How it is tested

Unit tests in
[`surfsense_local/backend/tests/unit/llm/catalog/local/`](../../../surfsense_local/backend/tests/unit/llm/catalog/local/)
cover the manifest, builds, the build choice and lead, the classifier, support,
pricing through the catalog (the badge matches the load on every budget shape; a
recommended build never warns), reprice, search against mocked transports, and
the service's installs; the routes are covered in
[`surfsense_local/backend/tests/integration/llm/`](../../../surfsense_local/backend/tests/integration/llm/),
and the screen in `download-chat-models.test.tsx`, `install-view.test.tsx` and the settings sections' `chat-models-settings.test.tsx` and `image-models-settings.test.tsx`.

## Known gaps

- Adding a `.gguf` from disk has no screen. A file copied into the models folder by hand shows on the next catalog fetch, with Use, but the router does not list it until it restarts, so choosing it fails until the next start, or until an install or delete rewrites the preset and Electron restarts the router ([`runtime.md`](runtime.md)).
- Chat sends text only, so a model that reads images never receives one.
- Deleting the image model in use removes its file while sd-server still has it open. Untested on Windows, which refuses to delete an open file, so there the delete may fail until sd-server is stopped first.
- A projector copied in by hand under its upstream name, such as `mmproj-F16.gguf`, pairs with nothing, and nothing says to rename it `mmproj-<model>.gguf`, so its model loads as text only.
- An install that fails after the weights landed but before the projector did writes no install record. The curated row then shows the build installed, matched by file name, and it loads as text only.
- A local manifest that fails to load is replaced by an empty one with no log line, so the curated rows vanish and nothing records why; the remote manifest logs its failure.
- No build is validated: `validated` is empty on all 129.
- `sampling`, `template.system_role`, the `image` defaults and llama.cpp's `run.args` are committed but nothing reads them, so chat does not use the publisher's sampling yet and sd-server runs at its own defaults. Only sd.cpp's `run.args` reach a runtime. `template.tools` and `template.reasoning` reach a row's support, which the screen does not show.
- A searched build's "Won't fit" is an estimate and keeps an enabled Download; the exact check at install is what refuses.
- `POST /llm/install` does not refuse a curated build that will not fit; only the screen's disabled Download does.
- A gated repo is marked "Needs an account", but the app sends no Hugging Face credential, so installing one of its builds fails with the generic install error.
- The API does not cache search and nothing debounces typing: once the query has two characters, every keystroke sends a request, unless the renderer's 300 s cache holds that exact query.
- A curated file that can no longer be fetched at its pinned commit, because the repo was deleted, gated or made private, gets the generic install error, and so does a checksum mismatch; nothing says which.
- The screen never marks the runtime unavailable, so installs stay enabled while llama-server is down.
- Nothing on the screen says whether sd-server is up: an image row reads In use as soon as it is chosen, while Electron starts sd-server on it a few seconds later. The hard-coded list's route reported that, and went with it.
- Nothing checks free disk space before a download starts.
- Browsing is still split by source, a catalog on the Add model page and one group per server, not the one list with Source and Capability filters the proposal describes.
