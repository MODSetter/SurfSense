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
its types (for an image model, the `tasks` its entry names: `generate` is `image_gen`, `edit` is `image_edit`), to which the route adds `selectable_for` ([`selection.md`](selection.md)), its support
(`context`, `reads_images`, `tools`, `reasoning`), whether the bundled runtime can
run it and why not, the `engine` that offered it, its builds, the build it leads
with and why, and the star. An audio row adds `voicing`: the memory measured while
voicing, the voice count and the languages, from its manifest entry. Each build is a set of files with roles, and carries
its fit, badge, whether it is installed, whether it is recommended, and whether it
reads images. An image or audio build's `fit` and `badge` are `null`: neither
sd.cpp nor audio.cpp has a fit estimate, so the row states the download size and
nothing about this machine, and nothing blocks its install. The screen renders these fields and computes none
of them.

`GET /llm/catalog/local` returns llama.cpp's rows, then sd.cpp's and audio.cpp's.
sd.cpp's are the six curated image models and two video models, only when Electron handed the API an
images folder, which it does only when it staged sd-server, in dev or packaged
([`index.ts`](../../../surfsense_local/electron/src/main/index.ts); [packaging](../packaging.md)).
audio.cpp's are the three curated audio models, only when Electron handed the API
an audio folder, which it does only when it staged audio.cpp's server.

## One slice per engine

Only what every engine shares lives at `catalog/local/`. Each engine is a slice
under [`engines/`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/), with its sub-parts grouped into folders:

```text
catalog/local/
  build.py  listed_file.py  quantization.py  classifier.py  installs.py  rows.py
  manifest/                 the entry envelope, strict config, loader, models.json
  install/                  plan.py, download.py (one path for every engine), tickets.py
  install_jobs/             jobs.py (queue, cancel, feed), steps.py, describe.py, router.py
  engines/
    engine.py               the seam: what every engine answers
    registry.py             which engine runs which type, and the entry fields each reads
    llamacpp/               engine.py, manifest_fields.py, support.py, pricing.py,
                            builds/, rows/, models_folder/, search/
    sdcpp/                  engine.py, manifest_fields.py, evidence.py,
                            builds/, rows/, images_folder/
    audiocpp/               engine.py, manifest_fields.py, evidence.py,
                            builds/, rows/, audio_folder/
  service.py  router.py  schemas.py  dependencies.py
```

[`engine.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/engine.py) is the one seam the service and the routes
speak to. Each engine answers where its files land (`folder`) and where each
file of a build lands in it (`landing`), its rows, whether it `holds` an installed model, the `check` before a download, the steps
`after_install` (llama.cpp rewrites the preset, waits for the router and warms
the model; sd.cpp has nothing to do, since sd-server takes its model at launch,
for the Studio job that needs it;
audio.cpp rewrites `server.json`), what to settle `after_remove` (audio.cpp
rewrites `server.json`), and what to do `on_startup` (llama.cpp writes the
preset; sd.cpp records legacy downloads; audio.cpp writes `server.json`). The selection an install fills is the
engine's `model_type` and `provider`.

| | [`engines/llamacpp/`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/) | [`engines/sdcpp/`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/) | [`engines/audiocpp/`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/audiocpp/) |
|---|---|---|---|
| Evidence | GGUF metadata keys | tensor names, as sd.cpp dispatches on them (`evidence.py`) | the family key, read from the header's front (`evidence.py`) |
| Manifest fields | `context` (required), `shape`, `template`, `sampling` | `image` defaults, or `video` ones for a video model: one of them (required) | `audio`: voices, languages, sample rate, measured memory (required) |
| Which files make a build | every build a repo offers, each with the repo's projector (`builds/in_repo.py`) | a GGUF at the repo's root, with the VAE and text encoder the entry names from their own repos (`builds/in_repo.py`) | every GGUF in the model's own folder of a shared repo, alone (`builds/in_repo.py`) |
| Default build | the first in a preference order led by `UD-Q4_K_XL` (`builds/choice/`) | the first the entry pins, in its reviewed order (`builds/choice.py`) | the first the entry pins, in its reviewed order (`builds/choice.py`) |
| Its folder | `models_folder/`: the scan, the preset, readiness | `images_folder/`: its files, where each lands, legacy downloads, the installed image; `launch.py`: its flags | `audio_folder/`: its files, the installed models, `server.json` |
| Also | support, pricing, the recommended build, the lead build, the star, search | | |

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
  needs `image` defaults, a video model `video` ones, never both, and an audio
  model needs `audio`, and none of them carries
  `context`, `shape`, `template` or `sampling`, because sd.cpp and audio.cpp read
  none of them. A field no engine reads would be reviewed and trusted while doing
  nothing. `validated` records `llama_cpp`, `sd_cpp` or `audio_cpp`, the runtime
  build a person ran the build on.
- **An audio model commits its voices and its memory**, because audio.cpp's server
  reports neither. `audio` holds the voices, each with an id, a label, a gender
  (`female` or `male`, from Kokoro's and Supertonic's voice ids and Kitten's
  `config.json`) and a language (none for a voice that speaks every listed
  language), the languages,
  the sample rate, and `peak_mb` measured while voicing at the server's default
  chunk size with every chunk full, since audio.cpp sizes its working memory for
  a request's longest chunk, with `chunk_steps`, smaller chunk sizes and their
  peaks, where one was measured. A model needs at least two voices, since a podcast has two
  speakers; ids do not repeat, and a voice speaks only listed languages.
- **`aliases` fold a download into its curated row.** A downloaded file shows as
  a curated build when its install record names the model's `source_repo`, an
  alias or a build's repo with the same quantization, or, with no record, when
  its file name is the build's own.

The shipped eighteen, most preferred first within each type. Seven
chat models, all from `unsloth/*-GGUF` with 18 builds each: Qwen3 32B, 14B, 8B,
4B, Gemma 3 4B (reads images), Qwen3 1.7B and 0.6B. Six image models. FLUX.2
klein 4B, Z-Image Turbo and ERNIE-Image Turbo, `Q4_0` then `Q8_0`, each a
diffusion GGUF with the text encoder and VAE sd.cpp's docs pair it with, from
their own repos: klein and Z-Image share `unsloth/Qwen3-4B-GGUF`'s `Q4_0`,
ERNIE takes Ministral 3 3B, and each takes its own VAE. LongCat-Image, `Q4_0`
then `Q8_0` from the `comfy/` folder of `vantagewithai/LongCat-Image-GGUF`,
runs with unsloth's Qwen2.5-VL-7B `Q4_0` and Z-Image's VAE, at the card's 50
steps. Then Stable Diffusion
1.5 and XL, one self-contained `Q4_0` file each from `kostakoff/*-GGUF`, the
same files and hashes the hard-coded list they replace downloaded. That list's
SDXL Turbo is not curated: its licence, `sai-nc-community`, fails the licence
rule ([Authoring](#authoring)). Two video models, sd.cpp's too: Wan2.1 T2V 1.3B
(`Q8_0` then `Q4_0`, from a repo holding only it, whose GGUF sd.cpp's docs do
not cite) leads while no clip is measured, then Wan2.2 TI2V 5B (`Q4_0` then
`Q8_0`, from `QuantStack`); both run with `city96/umt5-xxl-encoder-gguf`'s
`Q4_K_M` and each with its own Wan VAE. No image or video build is validated
yet. Three audio models, one file per build from their folders of
`audio-cpp/audio.cpp-gguf`: Kokoro 82M (`Q8_0`, then `BF16`), Supertonic 3 (`F16`,
then `orig`; its `q8_0` file is the `orig` file under another name) and KittenTTS
Mini 0.8 (`orig`). Only the three audio defaults are validated, each voiced on
audio.cpp v0.8.2. Each engine's catalog offers its own entries and skips the rest. `LocalManifest` rejects a wrong version, a repeated id or
quantization, an unpinned or unhashed file, a build without weights or with two
projectors, an entry no bundled engine runs, and any field it does not declare. A manifest that fails is replaced
at startup by an empty one, so downloaded models and search still work.

## Authoring

`scripts/refresh_local_manifest.py`, run by hand; never in CI, at packaging or
on a request path. `--only ID …` refreshes the named entries and keeps every other
one exactly as written, so adding a model does not re-pin the rest. `local_manifest/entries.py` is the hand-authored input:
which models, in which order, from which repo; `VALIDATED`, one in each
engine's `refresh.py`, is the other. For each repo the script reads the
commit sha, the file listing at that commit (sizes and `lfs.oid` hashes) and the
repo's `params` file, then the default build's header and its projector's header
over HTTP range requests. No weights are downloaded. Each engine reads its own
entries: `local_manifest/llamacpp/`, `local_manifest/sdcpp/` and
`local_manifest/audiocpp/` each hold a `refresh.py` (the network) and an
`assemble.py` (pure, the written entry).

- **An image entry's evidence comes from its tensors**, the only thing an sd.cpp
  file reliably states, and what a person reviews comes from the entry: the
  builds to pin, most preferred first, and the repo folder they sit in where
  the repo holds more than one conversion; the companions, each a VAE, text encoder
  or projector named by its repo and path and pinned at that repo's commit, with
  the vendor as `upstream_repo` where the repo is a copy; the `image` defaults,
  each with the source it was read from, or for a video model (`VideoEntry`)
  the `video` ones: the tasks it takes, its size, frames and rate, and its
  sampling; and sd-server's `run.args`. Only what
  the card, report or sd.cpp's docs state is filled; the rest is left to
  sd-server's defaults. It refuses a companion its repo no longer lists.
- **An audio entry's evidence is its family**, read from the default build's first
  64 KiB: audio.cpp writes it before the files it embeds, which make Kokoro's
  header 38.6 MB and Supertonic's 57 MB. The entry names the model's folder in
  the shared repo, its builds most preferred first, and the reviewed `audio` block.
- **It pins every chat build in the quantization preference order**
  ([`builds/choice/preference.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/builds/choice/preference.py)),
  and nothing outside it: no imatrix files, drafters, big endian builds, or
  quantizations such as `TQ1_0` that the order does not rank.
- **It refuses a model whose licence does not allow commercial use** with no
  revenue cap, registration, membership or excluded territory, before it reads
  anything: every entry's licence tag must be on the reviewed allowlist in
  [`local_manifest/licence.py`](../../../surfsense_local/backend/scripts/local_manifest/licence.py).
  An OpenRAIL or Gemma licence passes, since its use restrictions pass on to the
  user rather than limit commercial use. A unit test holds the committed
  manifest to the same rule, so a hand edit cannot slip one in.
- **It refuses to write** a build without a hash or size, a projector that does not
  see images or is not as wide as the model, and a refresh that drops a model or
  a build, listing what would go, unless it is rerun with `--accept-loss`.
- **`VALIDATED`**, one in each engine's `refresh.py`, names builds somebody ran,
  with the runtime build they ran it on: a chat build downloaded, chatted with
  and its citations confirmed to resolve. llama.cpp's and sd.cpp's are empty;
  audio.cpp's names the three default builds.

The script's assembly is tested over recorded input, with no network
([`test_local_manifest.py`](../../../surfsense_local/backend/tests/unit/scripts/test_local_manifest.py),
[`test_local_manifest_sdcpp.py`](../../../surfsense_local/backend/tests/unit/scripts/test_local_manifest_sdcpp.py),
[`test_local_manifest_audiocpp.py`](../../../surfsense_local/backend/tests/unit/scripts/test_local_manifest_audiocpp.py)).

## Which files make a build

llama.cpp's [`builds/in_repo.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/builds/in_repo.py)
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

For each curated chat model, in llama.cpp's [`builds/choice/`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/builds/choice/):

1. **The default**, blind to hardware: the first build in the preference order,
   `UD-Q4_K_XL` for every shipped chat model.
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
the first the entry pins). With no fit there is nothing to recommend or to fall
back from. A build is installed while every one of its files is on disk: when
the images folder's `installs.json` names its repo and quantization and every
file it records is there, or when each file is where its `landing` puts it. A
build missing one file offers Download, which fetches only what is missing, and
sd-server is never started on it. Each build carries `download_bytes`, what
Download would fetch, less the files another model already brought, and the
screen states that size until the build is on disk.

An audio row leads the same way, with the first build its entry pins as the
default. Its builds are installed only by the record: the audio folder's
`installs.json` must name the build's own file, still on disk. All three audio
models share one repo, and Supertonic and Kitten both have an `orig` build, so a
repo and a label would mark the wrong model installed.

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
`AUDIO_GEN`, audio.cpp's voice families among them (`kokoro_tts`, `supertonic`,
`kitten_tts`). Every audio.cpp file declares `general.architecture = audiocpp`,
speech recognisers included, so that name alone has its own typeless group,
"This model runs on audio.cpp. SurfSense runs only the voices in its list.", even
beside a text-to-speech tag. The tag only refuses or refines, never admits, and the tags that
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
encoder (`cond_stage_model.transformer.text_model.`) is `sd1`. The newer
families are named by the one tensor sd.cpp's `get_sd_version` dispatches each
on, bare in a standalone file and under `model.diffusion_model.` once sd.cpp
loads it: `double_stream_modulation_img.lin.weight` is `flux2`,
`cap_embedder.0.weight` is `z_image` and `layers.0.adaLN_sa_ln.weight` is
`ernie_image`, and `blocks.0.cross_attn.norm_k.weight` is `wan`, the one video
family, which the classifier makes `VIDEO_GEN`. LongCat is FLUX-shaped, and is
told from FLUX.1 as sd.cpp tells it: `double_blocks` with a `txt_in.weight`
3584 wide, Qwen2.5-VL-7B's hidden size where FLUX.1's T5 gives 4096. Its file
declares `flux`. Unsloth's ERNIE file declares
`general.architecture` `wan`, which is why the tensors decide. The refresh script writes the name into each image
entry's evidence, and sd-server's launch flags follow from it.

An audio.cpp GGUF's family is `audiocpp.model_spec.family`, and its header
embeds the model's voices and vocabulary, tens of megabytes past what the shared
header reader widens to. The audio.cpp slice walks the keys in order and stops at
the family, the seventh key in every curated file
([`engines/audiocpp/evidence.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/audiocpp/evidence.py)).
The refresh script writes it into each audio entry's evidence.

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
`builds/in_repo.py` uses. `full=true` returns every repo's file names, so this costs no
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

`POST /llm/installs` takes `{"catalog_id": "...", "select": true}`, and
optionally the `model_type` that `select` fills, the engine's first type when
absent, so onboarding's editing step installs straight into `image_edit`. Nothing
else: no repo, file, URL, path or quantization, so the renderer cannot name an
arbitrary download. A curated build's id is minted once per process and keyed on
its repo and weights path; a searched build's is a ticket holding the whole build
and the repo's tag, kept for 300 s, the window the screen's search cache uses.
Both fail the same way: `422 catalog id is stale or unknown; refresh the catalog`.

## Install jobs

An install is a job the API owns, not a request: `POST /llm/installs` answers
`202` with the job and returns, and the job runs on in the API whatever the
renderer does. A job carries its `id`, `catalog_id`, a `label` the screens show
(the row's name and build, or a searched repo's), the `model_types` its model
can fill (the row's `selectable_for`; a searched build fills `text_gen`),
`select`, `model_type`, and its latest `event`, one of the frames below. It ends
on `complete`, `error` or `cancelled`, and a finished job stays listed for 60 s,
so a screen that reconnects still learns how it ended
([`install_jobs/`](../../../surfsense_local/backend/modules/llm/catalog/local/install_jobs/)).

`GET /llm/installs/events` is NDJSON, `{"jobs": [...]}` per line: the whole list
at once, again on every change, and every 15 s even when nothing changed. Each
frame is complete, so a screen that missed one needs nothing replayed.
`DELETE /llm/installs/{id}` cancels a running or waiting job.

The renderer holds one copy: a query only that feed writes, opened once for the
app ([`installs/`](../../../surfsense_local/frontend/src/features/models/local/installs/)).
It toasts the end of a job it saw running, and refreshes the model queries when
one completes, whether or not Settings is open.

Event types:

```text
queued       "Waiting for the download ahead of it"   only while another install runs; it starts when that one ends
starting     "Checking the model"              every install; only a searched build's headers are read
error        the reason, and the job ends      when the exact check or the disk refuses
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
cancelled    "Installation cancelled"          DELETE reached it, running or waiting
```

The API fetches each file of the build from
`https://huggingface.co/{repo}/resolve/{revision}/{path}` into the models folder
itself, verifying every file against its sha256 (a searched file whose listing
gives no LFS hash goes unchecked): an in-process fetch is the only place
`egress.require()` can hold. Each file lands as a `.part` and is renamed
only when whole and verified, a cancelled download resumes with a `Range`
request, and a file already where it lands with its pinned hash is not fetched
again. One install runs at a time: a second job starts as `queued` and waits
rather than failing, so a model chosen while another downloads still comes.
Before any byte moves, the files not yet on disk plus 1 GiB must fit in the
disk's free space, or the job ends with how much room the download needs.
Then the install record is written,
`reprice()` rewrites the preset, the job waits for the router to list the
model and forwards its load progress, and with `select` the model becomes the
`text_gen` selection ([`runtime.md`](runtime.md)).

An image build takes the same steps into the images folder, with its record in
that folder's `installs.json`. Its weights keep their own name; every other file
lands once in the folder's `shared/`, as `<first 12 hex of its sha256>-<name>`,
since several models use the same VAE or text encoder and two different files
can share a name. The record lists them as `companions`. It skips both
`preparing` phases: sd-server takes its model at launch, so there is no router to
restart and nothing to warm. With `select` it becomes the `image_gen`
selection, and Electron starts sd-server on it when a Studio job needs it
([`../studio.md`](../studio.md)).

An audio build takes the same steps into the audio folder, with its record in
that folder's `installs.json`, and skips both `preparing` phases too. The install
rewrites `server.json`, which names every installed audio model with its family
and path; Electron restarts audio.cpp's server when the file changes, and a model
loads on its first request, so there is nothing to wait for. A Kitten entry also
carries the staged eSpeak-ng as `session_options`
(`kitten_tts.espeak_library_path` and `kitten_tts.espeak_data_path`): audio.cpp's
Kitten reads eSpeak only from there, not from the server's environment as Kokoro
does, and without it looks for a system eSpeak most computers lack. Electron
hands the API those paths as `SURFSENSE_LOCAL_AUDIO_ESPEAK_LIBRARY` and
`SURFSENSE_LOCAL_AUDIO_ESPEAK_DATA`, the same ones it gives the server.

Deleting a model removes every file its install record names that no other
installed build's record still names, every part of a split build and its
projector included, and forgets it: a shared VAE or text encoder goes with the
last model that uses it, worked out from the records at delete time. A file with no record, one copied
in by hand, loses only `<id>.gguf` and `mmproj-<id>.gguf`. `DELETE /llm/models/{name}`
finds the name in any engine's folder, and clears the selection of that engine's
type that named it. Deleting an audio model rewrites `server.json`; deleting the
last removes the file, since the server refuses an empty model list, and Electron
stops the server. At startup `warm()` rewrites `server.json` from the install
records, so a stale or missing file heals.

**Image models the hard-coded list downloaded** were saved as `sd15-q4_0.gguf`,
`sdxl-base-q4_0.gguf` and `sdxl-turbo-q4_0.gguf`, each verified against the
sha256 the manifest now pins. At startup `warm()` records each one as its curated
build ([`engines/sdcpp/legacy.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/images_folder/legacy.py)),
in place rather than renamed, since sd-server may hold it open, and revision
`0015` renames the selection that named it to the build's id.

## HTTP routes

All under `/llm`, in [`local/router.py`](../../../surfsense_local/backend/modules/llm/catalog/local/router.py);
installs are in [`local/install_jobs/router.py`](../../../surfsense_local/backend/modules/llm/catalog/local/install_jobs/router.py);
delete is in `modules/llm/router.py` beside the selection routes.

| Route | Returns | Network |
|---|---|---|
| `GET /llm/system` | budget, devices, `gpu_status` | none |
| `GET /llm/catalog/local` | budget, `gpu_status`, every local row, `recommended_id` | none |
| `GET /llm/catalog/local/search?q=&limit=` | hits, described not judged | `host:huggingface.co` |
| `GET /llm/catalog/local/search/{repo:path}` | the repo's row: builds with exact sizes and estimated fit | `host:huggingface.co` |
| `POST /llm/installs` | `202` and the job, queued behind any running one | `host:huggingface.co` |
| `GET /llm/installs` | every job, running, waiting, or finished in the last 60 s | none |
| `GET /llm/installs/{id}` | one job | none |
| `GET /llm/installs/events` | NDJSON: every job, now and on each change | none |
| `DELETE /llm/installs/{id}` | `204`; `404` when it is unknown or already over | none |
| `DELETE /llm/models/{model_name:path}` | `ModelDeleteRead`, with `selection_cleared` | none |

Search, repo reads and downloads share one consent, `host:huggingface.co`
([`../egress.md`](../egress.md)). A destination that is off is a `403` with
`code: egress_disabled`. An unreachable host is a `503` naming `huggingface.co`
on search and repo reads, and the job's generic error during an install.

## On the screen

Settings has one section per model type, **Chat**, **Image**, **Image editing**, **Video** and **Audio** in the nav, each headed **Text generation models**, **Image generation models**, **Image editing models**, **Video generation models** or **Audio generation models** on its own page.
Each names the model in use at the top, then groups the slot's models by source:
**This computer**, every build on disk, curated or not, with Use (when its type
can fill the slot) or In use and Delete after confirmation; then one group per
connected server ([`../connections.md`](../connections.md)). **Add model** opens
one page with both ways in, laid out alike, no card or border around either:
**Use a server**, collapsed to a Connect button until opened, because it is
short, then **On this computer**, the catalog below. Both sections read the
one `GET /llm/catalog/local`: chat takes llama.cpp's rows, image and image
editing and video take sd.cpp's that can fill their slot (`selectable_for`), and audio
takes only audio.cpp's, each curated model with its size and a
Download. Once a chat or image model is on disk its row offers Delete after
confirmation, the same as **This computer**'s list; an audio row reads
Downloaded. An audio row reads on one line: its build, its size, the memory it
takes while voicing, its voice count and its languages, counted, or named when
there is one ("orig · 302 MB · 1.9 GB while voicing · 8 voices · English"), from
the row's `voicing`. The catalog carries sd.cpp's rows only when the API has an
images folder, and audio.cpp's only when it has an audio folder, which Electron
hands it only when that server is staged, in dev or packaged
([`../packaging.md`](../packaging.md)); otherwise that section's part of the
page says those models cannot run on this computer, and the layout stays the
same.

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

- The install button names the phase ("Waiting…", "Starting…", "Downloading…",
  "Verifying…", "Preparing…", "Selecting…"), and the progress bar and Cancel sit under the build being
  installed, curated or searched. "Other builds" stays open while one of its
  builds installs.
- A download blocks nothing but itself: every other Download stays enabled and
  queues behind it, reading "Waiting…". Delete is off while any job runs, since
  the API refuses one then.
- Reduced speed installs like any other build, with no confirmation. Only a
  refusal blocks.
- Install errors, including the exact check's refusals, show as a toast.
- An install belongs to the API, not the page that started it: leaving the
  Add model page, closing Settings or reloading does not cancel it. Each
  section's list shows the jobs whose model can fill its slot, wherever they
  were started, until they end: a video download shows under Video and nowhere
  else, and FLUX.2 klein under both Image and Image editing.
- The image section uses the same cards, install states and progress as chat;
  it only downloads without selecting, so a model is chosen with Use once it is
  on disk. Every downloaded model has Delete, the one in use included: the API
  clears every slot that named it, and Electron stops sd-server on its next poll.
- The image editing section is the image section's parts for `image_edit`: only
  models whose entry names `edit`, each marked In use by the build's
  `selected_for`, which lists the slots that chose it, so FLUX.2 klein in use for
  images still offers Use for editing, with nothing to download.
- The audio section has the same install states, Use, In use and Delete as
  image, and its rows add what voicing takes. Every downloaded model has Delete,
  the one in use included: the API refuses while Studio is generating, otherwise
  it clears the audio slot and rewrites `server.json`, and Electron restarts
  audiocpp_server on its next poll. The voice the app ships is the exception:
  it is part of the install, read in place from the models pack, so it has no
  Delete, and the API refuses one.

## How it is tested

Unit tests in
[`surfsense_local/backend/tests/unit/llm/catalog/local/`](../../../surfsense_local/backend/tests/unit/llm/catalog/local/)
cover the manifest, builds, the build choice and lead, the classifier, support,
pricing through the catalog (the badge matches the load on every budget shape; a
recommended build never warns), reprice, search against mocked transports, and
the service's installs, install jobs (`test_install_jobs.py`), the audio.cpp slice's evidence and rows, and each
engine's refresh assembly; the routes, audio's `server.json` included, are
covered in
[`surfsense_local/backend/tests/integration/llm/`](../../../surfsense_local/backend/tests/integration/llm/), the feed over a real socket in `test_install_feed.py`,
and the screen in `download-chat-models.test.tsx`, `install-view.test.tsx` and the settings sections' `chat-models-settings.test.tsx`, `image-models-settings.test.tsx` and `audio-models-settings.test.tsx`.

## Known gaps

- Adding a `.gguf` from disk has no screen. A file copied into the models folder by hand shows on the next catalog fetch, with Use, but the router does not list it until it restarts, so choosing it fails until the next start, or until an install or delete rewrites the preset and Electron restarts the router ([`runtime.md`](runtime.md)).
- Chat sends text only, so a model that reads images never receives one.
- Deleting the image or audio model in use removes its file while sd-server or audiocpp_server may still have it open. Untested on Windows, which refuses to delete an open file, so there the delete may fail until that server is stopped first.
- A projector copied in by hand under its upstream name, such as `mmproj-F16.gguf`, pairs with nothing, and nothing says to rename it `mmproj-<model>.gguf`, so its model loads as text only.
- An install that fails after the weights landed but before the projector did writes no install record. The curated row then shows the build installed, matched by file name, and it loads as text only.
- A local manifest that fails to load is replaced by an empty one with no log line, so the curated rows vanish and nothing records why; the remote manifest logs its failure.
- Only the three audio defaults are validated; `validated` is empty on every other build.
- `sampling`, `template.system_role` and llama.cpp's `run.args` are committed but nothing reads them, so chat does not use the publisher's sampling yet. sd.cpp's `image` defaults and `run.args` reach sd-server as launch flags. `template.tools` and `template.reasoning` reach a row's support, which the screen does not show.
- A searched build's "Won't fit" is an estimate and keeps an enabled Download; the exact check at install is what refuses.
- `POST /llm/installs` does not refuse a curated build that will not fit; only the screen's disabled Download does.
- A gated repo is marked "Needs an account", but the app sends no Hugging Face credential, so installing one of its builds fails with the generic install error.
- The API does not cache search and nothing debounces typing: once the query has two characters, every keystroke sends a request, unless the renderer's 300 s cache holds that exact query.
- A curated file that can no longer be fetched at its pinned commit, because the repo was deleted, gated or made private, gets the generic install error, and so does a checksum mismatch; nothing says which.
- The screen never marks the runtime unavailable, so installs stay enabled while llama-server is down.
- Nothing on the screen says whether sd-server is up: an image row reads In use as soon as it is chosen, while Electron starts sd-server on it only when a Studio job needs it. The hard-coded list's route reported that, and went with it.
- The `audio` block's `chunk_steps` are committed but nothing reads them: short of memory at the default chunk, a podcast refuses rather than stepping down, until a listening test clears the smaller chunks.
- Browsing is still split by source, a catalog on the Add model page and one group per server, not the one list with Source and Capability filters the proposal describes.
