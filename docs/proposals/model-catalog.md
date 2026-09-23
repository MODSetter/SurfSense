---
status: in-progress
code:
  - surfsense_local/backend/modules/llm/model_type.py
  - surfsense_local/backend/modules/llm/catalog/
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/backend/scripts/
  - surfsense_local/frontend/src/features/model-catalog/
  - surfsense_local/frontend/src/features/model-selection/
  - surfsense_local/frontend/src/features/connections/
---

# The model catalog

> Every model the app can use is classified from a packaged manifest, offline, and shown in one screen filtered by source (local, remote) and by capability (the model's type). Local and remote are two catalogs that share one vocabulary and nothing else.

This reworks the local catalog ([`catalog.md`](../architecture/local-models/catalog.md)), the hard-coded sd.cpp list, and the per-connection model lists ([`connections.md`](../architecture/connections.md)). Those docs describe the code as it stands, including the parts of this design already built. They constrain this design only where a decision below says so.

## What this replaces

Until this work ships, `docs/architecture/` describes the code as it is and this proposal describes where it is going; `catalog.md` and `connections.md` say at their top what is still to come. When it ships, the pages change as follows and this proposal is deleted.

| Architecture page | Today | When this ships |
|---|---|---|
| [`local-models/catalog.md`](../architecture/local-models/catalog.md) | the local catalog: curated manifest, install gate, search | replaced by `model-catalog/local.md`, and deleted |
| [`connections.md`](../architecture/connections.md) | connections, and how their models are listed and classified | keeps storage, keys, the probe and the runtime; model listing moves to `model-catalog/remote.md` |
| [`local-models/selection.md`](../architecture/local-models/selection.md) | one model per `ModelType` | done in step 1 |
| [`data-model.md`](../architecture/data-model.md) | `selected_models.model_type` (step 1) and the provider id on a connection (step 3b) | done |
| [`studio.md`](../architecture/studio.md) | the `image_gen` selection (step 1) and the hard-coded sd.cpp list | the local manifest |

Known gaps in `local-models/catalog.md` that step 5 closed:

- A vision model installs as text only: a build's `files[]` carries its projector (step 5).
- Downloads are not checksum-verified: every file has a `sha256` (step 5).
- Curated rows send `context_length: 0`: `context` is in the manifest (step 5).
- A dead curated pin gets the generic install error: files are pinned to a commit, so a re-upload, rename or deletion on `main` no longer breaks a shipped manifest; a deleted repo still does (step 5).

## The shape of it

Each side runs the same four steps, with its own evidence:

```text
manifest ─► classifier ─► support ─► catalog ─► rows
(packaged)  (what is it)  (what can  (what the user
                           it do)     sees, and can do)
```

| Step | Local | Remote |
|---|---|---|
| Manifest | curated GGUF builds from Hugging Face, text and image | every provider and model models.dev lists |
| Classifier | GGUF architecture, pipeline tag, file kind → type | modalities, context window, name → type |
| Support | context window, reads images (projector), tools (chat template) | tool call, reasoning, structured output, context window, reads images |
| Catalog | manifest + downloaded files → rows | manifest + connections' live listings → rows |
| Live extension | Hugging Face search, opt-in, same classifier | none: the manifest is the catalog |

**Why two catalogs.** Local and remote share almost nothing: a local model is a repo and a file, is priced for this machine and is downloaded; a remote model is a connection and an id, needs a key and is tested. One generalised shape over both is where maintenance and debugging break. They share only the words the screen filters on and selection is keyed by.

**Why a packaged manifest.** Listing and classifying never need the network. The catalog renders on first paint, on an airgapped machine, and every classification rule is a unit test over a committed fixture.

## The shared vocabulary

Two enums, and the only words local and remote share:

```python
# modules/llm/model_type.py: a primitive of the whole llm module
class ModelType(StrEnum):          # what a model is for
    TEXT_GEN = "text_gen"
    IMAGE_GEN = "image_gen"
    IMAGE_EDIT = "image_edit"
    VIDEO_GEN = "video_gen"
    AUDIO_GEN = "audio_gen"

# modules/llm/catalog/source.py
class Source(StrEnum):             # where a model comes from
    LOCAL = "local"
    REMOTE = "remote"
```

`ModelType` sits at the root of `modules/llm/`, not inside `catalog/`, because it is more than a filter: the classifiers produce it, the catalogs filter on it, and selection, the database and the pickers key on it. `Source` is only the catalog's filter.

- **A type is a filter, a support is a badge.** Reading images (the **Vision** badge) does not make a model an image model. Each side's support is its own dataclass, because the fields each can know differ.
- **None is not no.** A support field is `None` when the evidence is silent, as `catalog/remote/support.py` holds for models.dev.
- **Unknown is a state, not a type.** A remote id nothing recognises has no types and `known=False`. The capability filter offers "Unknown" only when such rows exist.
- **One word per idea.** `completion`, `image_generation` as a capability, and the curated `vision` go.

### A type is a selection

There is no separate list of roles. A role would be a second word for each type: `generation` was `TEXT_GEN` and `image_generation` was `IMAGE_GEN`, one to one. So the type is the selection, and the user picks one model for each `ModelType`:

- **`selected_models` is keyed by type.** The column `role` becomes `model_type`, its CHECK lists the five values, and a hand-written migration maps `generation` to `text_gen` and `image_generation` to `image_gen`. The provider CHECK follows: `llamacpp` only for `text_gen`, `sdcpp` only for `image_gen`, `openai_compatible` for any.
- **One rule decides who can fill a slot.** A model can be selected for a type when its classification contains that type, or when it is unknown. Selection, the catalog and the pickers read the same rule, so a model is selectable everywhere or nowhere.
- **Every type is listed and selectable**, including those no feature reads yet. Chat, titles and Studio's writing read `text_gen`; Studio's images read `image_gen`; `image_edit`, `video_gen` and `audio_gen` have no reader yet, and their setting says so rather than hiding. The feature that first reads one brings the client that calls it.
- **Adding a type is adding an enum value**, the classifier groups that emit it, and a CHECK migration.

A second role over one type, such as a separate model for titles, would bring a mapping back. It is introduced when such a role exists, with the case in front of it, not before.

## Manifests

Both are source, not build output. A script refreshes one, a person reads the diff in a pull request, and packaging bundles the committed file. Packaging never fetches: an unreviewed upstream change would ship, and rebuilding an old tag would produce a different app.

A manifest holds **evidence, not verdicts**. The classifier runs at runtime over the committed fields, so fixing a rule takes effect without regenerating the file.

### Local

`catalog/local/manifest/models.json`, built by `scripts/refresh_local_manifest.py`. Text and image models live in one list, because they are one source, GGUF files on Hugging Face, and one shape; the evidence says which type each is.

A local model differs from a remote one in that the user downloads files and runs them on this machine. Beyond classifying and displaying it, the manifest makes three things reliable: the download (exact files, verified), the fit (will it run here), and the launch (how the runtime starts it).

```jsonc
{
  "schema_version": 1,
  "refreshed_at": "2026-09-23",
  "models": [                                   // position = preference, within each type
    {
      "id": "qwen3-8b",
      "name": "Qwen3 8B",
      "family": "Qwen3",
      "publisher": "Qwen",
      "description": "Balanced chat model for documents, fits 16 GB machines",
      "license": "apache-2.0",
      "source_repo": "Qwen/Qwen3-8B",
      "aliases": ["Qwen/Qwen3-8B", "unsloth/Qwen3-8B-GGUF", "bartowski/Qwen_Qwen3-8B-GGUF"],

      "evidence": {                             // what the classifier reads
        "architecture": "qwen3",                // the chosen file's own header
        "pipeline_tag": "text-generation",      // weak evidence: often missing or wrong
        "parameters_b": 8.2
      },

      "context": 40960,
      "template": { "tools": true, "reasoning": true, "system_role": true },

      "sampling": {                             // reviewed; null for image models
        "origin": "unsloth/Qwen3-8B-GGUF@3f2a…/params",
        "thinking":     { "temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0 },
        "non_thinking": { "temperature": 0.7, "top_p": 0.8,  "top_k": 20, "min_p": 0.0 }
      },
      "image": null,                            // image models: { "resolution": 1024, "steps": 20,
                                                //   "cfg": 4.0, "sampler": "euler", "flow_shift": 3.0, "origin": "…" }

      "shape": { "block_count": 36, "head_count_kv": 8, "…": "…" },   // text only

      "builds": [                               // smallest first; the order carries no preference
        { "quantization": "Q3_K_M", "…": "…" },
        { "quantization": "Q4_K_M", "…": "…" },
        {
          "quantization": "UD-Q4_K_XL",         // the label as the quantizer names it, UD- prefix kept
          "files": [
            {
              "role": "weights",                // weights | projector | drafter | vae | text_encoder
              "repo": "unsloth/Qwen3-8B-GGUF",
              "upstream_repo": null,            // the vendor repo, when this one is a byte-for-byte mirror
              "revision": "3f2a…",              // a commit sha
              "path": "Qwen3-8B-UD-Q4_K_XL.gguf",   // a split build lists every part
              "size_bytes": 5100000000,
              "sha256": "…"
            }
            // a vision build adds { "role": "projector", "path": "mmproj-F16.gguf", … } with the same pins
          ],
          "run": { "args": [] },
          "validated": { "llama_cpp": null }    // the runtime build a person ran it on
        },
        { "quantization": "Q6_K", "…": "…" },
        { "quantization": "Q8_0", "…": "…" }
      ]
    }
  ]
}
```

| Part | Reliability | Experience |
|---|---|---|
| `evidence` | one classifier for everything local: a manifest entry, a downloaded file's header and a search hit all produce this same object | the capability filter |
| `aliases` | a file the user downloaded from another repo holding the same model, such as the vendor's or another quantizer's, is recognised as this entry | a searched download of a curated model shows as that model |
| `context`, `template` | chat sizes its history to the real window; the tool and reasoning flags are there for the later chat rework | badges such as Vision and long context |
| `sampling` | each model runs with its publisher's settings, and a hybrid model with the right ones for each mode, not one set for every model | better answers with no settings to learn |
| `image` | Studio generates with the model's native size, steps, guidance and sampler | sensible defaults per image model |
| `shape` | the fit estimate and the recommendation, offline | Fits, Reduced speed, Won't fit |
| several `builds` | each model recommends one build for this machine ([Which build of a model](#which-build-of-a-model)), so a machine that cannot run the default gets a smaller build of the same model | the best quality this machine can run at a usable speed |
| `files[]` and `role` | a model is a set of files: vision needs a projector, a multi-token-prediction model a drafter, FLUX a VAE and text encoders, a split build every part. The downloader fetches the set, and whether the app can run a model is whether its runtime supports every role | vision and image models work after download; a multi-file model is a manifest entry, not new code |
| `revision`, `upstream_repo` | a quantizer re-uploading, renaming or deleting a file cannot change what is downloaded; a mirror names what it copies | no failed download on a model that worked last month |
| `sha256`, `size_bytes` | every download is verified | an honest progress bar and a real verification step |
| `run.args` | launch flags are tested and committed, not hard-coded per model | image models that do not run out of memory while decoding |
| `license`, `publisher`, `source_repo` | nothing curated needs a Hugging Face account | who made it, under which licence, and where to read more |
| position, `validated` | the recommendation reads position; `validated` names the runtime build a person ran this exact build on, because some quantizations run only on newer or forked llama.cpp | "Recommended for this computer" |

- **`id` is ours**, not a Hugging Face repo: a build comes from a quantizer's repo, and an image model's files from several.
- **Vision is a file, not a label.** A build that reads images lists its projector in `files[]`; there is no `capabilities` field and no `"vision"` string to keep in step with it. The old manifest's `capabilities`, `mmproj`, `variants`, `model_id` and `decode_fraction` went: the first three become `files[]` roles and `builds`, `model_id` becomes `id` and `source_repo`, and nothing reads `decode_fraction`.
- **Every file is pinned to a commit.** Quantizers change repos in place: Unsloth renamed, moved and deleted files on `main` of a published repo, and re-uploads fixed chat templates under the same name.
- **`template` is read at refresh time** from the chat template in the header, so the catalog never loads a model to say what it supports.
- **Nothing but the quantization label is taken from a filename.** Not size, not parameter count, not architecture: a catalog that did so got 99.6% of its sizes wrong. The label is the exception because it has no other source: `UD-Q4_K_XL` is a quantizer's naming convention, and the header's `general.file_type` names the same file by its base type. The label is read with its prefix kept; a parser that reads `UD-Q4_K_XL` as `Q4_K_XL`, as search's did before `quantization.py`, would never match the top of the preference order.

The three image models hard-coded in `providers/sdcpp/` become entries like any other.

### The curation path

`scripts/refresh_local_manifest.py`, run by hand, output reviewed in a pull request. Six steps, each owned by a person or the script:

1. **A person chooses the models.** Their order, `name`, `description`, `aliases`, and which repo each build comes from, preferring an ungated mirror of a gated vendor repo and recording the vendor as `upstream_repo`.
2. **The script resolves builds.** For each model it pins every build whose quantization is in the preference order ([Which build of a model](#which-build-of-a-model)), not only the default, so a machine that cannot run the default has a smaller build of the same model to step down to. It uses the same file-picking rules search uses (`catalog/local/builds.py`): skip imatrix files and big-endian builds; take the first shard of a split set and list every part; count weights at the root and in folders named after a quantization (`BF16/`), the root winning a quantization both hold, and nothing in any other folder; leave out drafters (`mtp`, `draft`, `dflash`, `eagle`), which nothing runs yet; attach the repo's projector, preferring F16, to every build, and confirm it by its header (`general.type` is `mmproj`, it sees images, and it is as wide as the model).
3. **The script reads evidence** from each chosen file's own header over HTTP range requests, never from the repo-level `gguf` metadata Hugging Face serves, which describes one arbitrary file in the repo. `revision`, `size_bytes` and `sha256` come from the repo's file listing (`lfs.oid`) at a pinned commit. No weights are downloaded.
4. **The script proposes run defaults; a person reviews them.** Sampling comes from the repo's machine-readable `params` file where one exists, with its source in `origin`, because published settings disagree with each other between a model card, its docs and its example commands. Image settings are proposed per family and reviewed the same way.
5. **The script guards itself.** It refuses to write a build it could not read completely, so nothing unknown can be recommended; refuses a refresh that drops models or builds without the person naming them; and flags a chat template that differs between the pinned revision and `main`, which is how a quantizer ships a fix.
6. **A person validates.** Downloading a build, chatting with it and confirming citations resolve sets `validated.llama_cpp` to the runtime build it ran on.

The script is tested against recorded Hugging Face responses, so a change in how it reads a listing is caught in a test rather than in a shipped manifest.

### Remote

`catalog/remote/manifest/models.json`, built by `scripts/refresh_remote_manifest.py`, which replaced `fetch_model_capabilities.py`. It keeps models.dev's nesting, provider then models, in the app's own words: models.dev is written for the Vercel AI SDK, and its `npm` and `env` fields name JavaScript packages and environment variables this app never uses. The script translates them into what the app does with a provider.

```jsonc
{
  "schema_version": 1,
  "source": "https://models.dev/api.json",
  "refreshed_at": "2026-09-23",
  "providers": {
    "openai": {
      "name": "OpenAI",
      "doc": "https://platform.openai.com/docs/models",
      "connect": {
        "status": "ready",              // ready | needs_account_details | needs_url | unreachable
        "base_url": "https://api.openai.com/v1",
        "base_url_origin": "reviewed",  // models.dev | reviewed
        "account_fields": [],           // [{"name": "DATABRICKS_HOST", "label": "Databricks host"}]
        "key": "required",              // required | none
        "local": false,                 // a loopback server: no key, no egress question
        "reason": null                  // set when unreachable
      },
      "models": {
        "gpt-5-nano": {
          "name": "GPT-5 Nano",
          "family": "gpt-nano",
          "description": "Tiny GPT-5 lane for routing, extraction, classification, and bulk jobs",
          "release_date": "2025-08-07",
          "status": null,               // null | beta | deprecated

          "modalities": { "input": ["text", "image"], "output": ["text"] },
          "context": 400000,

          "output_limit": 128000,
          "tool_call": true,
          "reasoning": true,
          "reasoning_options": [{ "type": "effort", "values": ["minimal", "low", "medium", "high"] }],
          "structured_output": true,     // null when models.dev never said
          "temperature": false,

          "call": null                   // {"route": "responses"} or {"protocol": "anthropic"} when it differs
        }
      }
    }
  }
}
```

| Group | Fields | Reliability | Experience |
|---|---|---|---|
| Connect | `status`, `base_url`, `account_fields`, `key`, `local`, `reason` | a provider the app cannot call is never offered as if it could be | the connection form asks for exactly what the provider needs, and an unreachable one says why |
| Classifier evidence | `modalities`, `context` | classification is re-run offline over committed evidence | the capability filter |
| Support evidence | `output_limit`, `tool_call`, `reasoning`, `reasoning_options`, `structured_output`, `temperature` | a request sends only parameters the model accepts, and chat sizes its history to the real window instead of a fixed budget | fewer failures mid-chat |
| Call | `call` | a model served only on `/responses` (21 today) or through another protocol (147) is unreachable with a reason, not a failure on the first message | the reason on the row |
| Display | `name`, `family`, `description`, `release_date`, `status` | | readable names, grouping by family, newest first, deprecated hidden by default and still named on a selection that uses one |

**How `connect` is derived.** models.dev writes a base URL (`api`) only for providers reached through the generic `@ai-sdk/openai-compatible` package; a provider with its own package has the URL built into that package. So:

| Case | Evidence | `connect` |
|---|---|---|
| URL stated, OpenAI protocol | `api` with an OpenAI-style package, 184 of 223 providers | `ready`, `base_url_origin: models.dev` |
| URL stated, another protocol | `api` with `@ai-sdk/anthropic` or a vendor package: MiniMax, Subconscious and six more | `unreachable`: "Speaks Anthropic's API, which SurfSense does not" |
| URL is a template | `${VAR}` in `api` (Databricks, Cloudflare Workers AI, Infomaniak and two more) | `needs_account_details`, `account_fields` from the variables |
| No URL, one fixed endpoint | own SDK, OpenAI-compatible endpoint verified (OpenAI, Groq, Mistral, xAI, Together, Cerebras, Gemini) | `ready` from the reviewed table, `base_url_origin: reviewed`: 7 providers |
| Not a bearer key | Amazon Bedrock (AWS signing), Google Vertex (Cloud sign-in) | `unreachable`, with the reason, from the reviewed table |
| No URL and no entry | Azure, SAP AI Core, watsonx, and endpoints not yet verified such as Anthropic, DeepInfra and Perplexity: 16 providers | `needs_url`: the user enters it |
| Loopback URL | LM Studio and three more | `key: none`, `local: true` |

`npm` is not a reachability test on its own: Groq, Mistral, xAI and Together have their own package and serve the OpenAI API. The reviewed table is where a person decides it, once per provider, in a pull request.

**The reviewed table** (`scripts/remote_manifest/endpoints.py`) only fills what models.dev cannot say: a hosted provider's fixed OpenAI-compatible URL where its SDK hides it, or why a provider is unreachable. It never overrides a URL models.dev states, and it holds nothing that depends on the user. A URL is added once someone has checked it against the provider's docs, and the entry cites where; until then the provider is `needs_url`, never a guess. The refresh script flags an entry whose provider left models.dev.

**The user has the last word on every URL.** Picking a hosted provider fills its URL in, and the field stays editable, so a company proxy or gateway in front of it works. A local server (Ollama, vLLM, llama.cpp's server, a machine on the network) is not in the table at all: its port is whatever the user configured, so the form asks for the URL, with examples as placeholder text only, and the save probes `GET {url}/models` as it does today. Loopback needs no key and no egress decision. Offering the local servers actually answering on this machine is a possible later improvement, not a preset.

**Left out:** `cost`, because a list price refreshed a few times a year is wrong more often than it helps, differs from what a user with discounts, caching or a free tier pays, and billing is out of scope; the provider's `doc` link is on the row instead. `npm` and `env` are translated, not copied. `attachment` repeats the input modalities. `knowledge`, `interleaved` and `open_weights` have no reader. At this shape the file is about 4 MB, most of it `description`.

**A remote model's identity is `provider/model`.** `openai/gpt-5-nano` and `openrouter/qwen/qwen3.7-max`. The same model id appears under many providers (1,114 of 3,814 ids), and each provider's entry describes what that provider serves, which differs for 407 of them: `deepseek/deepseek-v3.2` takes PDFs on one provider and text only on nine others. Keyed by provider, nothing collides and nothing is merged. OpenRouter is one provider among the others, not an exclusion.

The snapshot this replaced dropped the provider and keyed by model id alone. That is what forced it to merge disagreeing entries by majority, to exclude OpenRouter, and to store two derived strings instead of the evidence, which is why embedders read as chat models.

## Local

### Classifier

`catalog/local/classifier.py`: an `evidence` object in, a type or known-none out. The manifest stores that object; for a downloaded file it is read from the header, and for a search hit from the candidate build's header and the repo's tag. It replaced the denylist in the former `catalog/search/not_chat.py`, which answered only "chat or refuse", with groups that each answer a type:

- Diffusion architectures (`sd1`, `sdxl`, `sd3`, `flux`, `flux2`, `qwen_image`, `z_image`, `lumina2` and the rest) are `IMAGE_GEN`. They were refused because the old catalog was text only; the app ships sd.cpp.
- Video architectures (`wan`, `ltxv`, `hyvid`, `cosmos`) are `VIDEO_GEN`.
- Text-to-speech models are `AUDIO_GEN`.
- Embedders, rerankers, speech recognisers, labellers, OCR, draft heads and projectors are known-none: no type describes what they produce.
- Any other architecture is `TEXT_GEN`. A denylist ages the right way: an unknown architecture is usually a chat model released last week.

Evidence rules:

- **The chosen file's own header**, never the repo name and never the repo-level `gguf` metadata, which describes one arbitrary file in the repo.
- **No single field decides.** The architecture alone misleads: a text-to-speech model declares `llama`, a speech recogniser `qwen3`, and embedders and rerankers declare chat architectures. The pipeline tag alone misleads too: it is often missing, including on repos that ship a projector. The groups key on both, and the tag only ever refuses or refines, never admits.
- **A projector is known by its header**: `general.type` is `mmproj`, and `clip.has_vision_encoder` and `clip.has_audio_encoder` say which inputs it serves. That is how a downloaded model with no manifest entry gets "reads images".
- **An unreadable header fails open to `TEXT_GEN`**, marked approximate, because refusing on a failed read hides models the user can run.

### What a type is, and whether the app can run it

Two answers the old code gave as one refusal. The classifier says a FLUX GGUF is `IMAGE_GEN` and a Wan GGUF is `VIDEO_GEN`. Both are listed; the app ships no runtime for video or speech, so a local `VIDEO_GEN` or `AUDIO_GEN` row is not runnable, "SurfSense cannot run video models yet", and the same model from a remote provider can still be selected. The catalog says whether this app can run it: a model is runnable when its runtime supports every file role it needs and the app knows every file. A curated FLUX entry lists its VAE and text encoders and is runnable. A FLUX build found by search is one file with no known companions, so its row is `IMAGE_GEN`, not runnable, "Needs files SurfSense cannot find on its own".

### Support, and reading images

`catalog/local/support.py` says what a build can do, for every local row, curated or not:

```python
LocalSupport(
    context: int | None,       # the trained window
    reads_images: bool,        # the build ships a projector with a vision encoder
    tools: bool | None,        # from the chat template; None when there is none to read
    reasoning: bool | None,
)
```

The two sources give the same object. A curated build's support comes from the manifest: `context`, `template`, and whether `files[]` has a `projector`. A downloaded file or a searched repo's comes from headers: the model's own header for `context` and the template, and the projector's header (`general.type` is `mmproj`, then `clip.has_vision_encoder`) for whether it reads images.

Images are the only input beyond text this work shows. llama.cpp also takes audio through a projector with an audio encoder (`clip.has_audio_encoder`), but nothing in the app sends audio, so an audio-only projector earns no badge and is not part of a build's file set. Audio is one more field and one more badge when a feature needs it.

`reads_images` is a plain boolean, because it describes this install and not the model family: weights without their projector cannot see, whatever the base model could. It is a badge, never a type: a vision chat model is `TEXT_GEN` that reads images.

A vision build is whole only with its projector, so:

- **The downloader fetches both**, as one build's file set, and records the pairing in the models folder's install record, saving the projector as `mmproj-<model>.gguf` so two vision models never share or overwrite one. A projector merely sitting beside a model is never attached to it.
- **Fit prices both.** The footprint is the sum of the build's files, passed to `estimate()` as `mmproj_bytes` for the projector, so the recommendation never picks a build that fits only until the projector loads.
- **The runtime loads both.** The preset names the recorded projector, or one saved under the model's name, only when its header sees images and matches the model's width, and `providers/llamacpp/capabilities.py` still decides at load time whether the running model can take an image (the runtime reports an image input and the template takes typed content). The catalog's `reads_images` is what can be known before a download; the runtime's answer is what chat trusts.

Sending an image to a local model in a chat is not part of this work: chat sends text only today. Until chat's own change lands, Vision describes the model and the build, not a feature of the chat screen.

### Catalog

`catalog/local/catalog.py` is a pure function: the manifest and the list of downloaded files in, rows out.

| Input | What it is | Network |
|---|---|---|
| Manifest | the models we picked, packaged | none |
| Downloaded files | what the user already downloaded into the models folder: from the manifest, from search, or copied there by hand | none |

Nothing is pre-installed; the app ships no model weights. A downloaded file is an input because its row offers Use and Delete instead of Download. A file whose repo is a manifest entry's `aliases` is shown as that entry. Any other, downloaded from search or copied by hand, is in no manifest: its own header is the only evidence, and the same classifier reads it. Header reads are cached on path, size and modification time, so a folder of large files is read once.

**One row shape for every local row**, whatever its origin:

```jsonc
{
  "id": "qwen3-8b",                  // curated id, or repo and file for any other
  "source": "local",
  "origin": "curated",               // curated | downloaded | search
  "name": "Qwen3 8B", "family": "Qwen3",
  "types": ["text_gen"], "known": true,
  "selectable_for": ["text_gen"],    // selectable.py, the rule remote rows use
  "support": { "context": 40960, "reads_images": false, "tools": true, "reasoning": true },
  "runnable": true, "not_runnable_reason": null,
  "builds": [
    { "catalog_id": "…", "quantization": "UD-Q4_K_XL", "footprint_bytes": 5100000000,
      "fit": { … }, "badge": { … }, "can_install": true, "installed": false, "recommended": true }
  ],
  "default_quantization": "UD-Q4_K_XL",   // null unless curated
  "recommended": true                     // the model-level star; false unless curated
}
```

| | curated | downloaded, in no manifest | search |
|---|---|---|---|
| evidence and support | manifest | the file's header | the candidate build's header and the repo's tag |
| `builds` | every pinned build | the file on disk | every build in the repo |
| `default_quantization`, a build's `recommended` | set | null, false | null, false |
| the row's `recommended` | can be true | false | false |
| `reads_images` | a build lists a `projector` | a projector sits beside the file | the repo ships a projector |

The screen renders these fields and computes none of them: no fit, no default, no recommendation, no selectability.

**The recommendation** walks the manifest from the most preferred model down. For each model it asks for that model's recommended build ([Which build of a model](#which-build-of-a-model)), and the first model with one wins, so a machine one gigabyte short of `UD-Q4_K_XL` gets the same model at `Q4_K_M` rather than a model half its size.

### Which build of a model

Each curated model recommends one of its builds for this machine. The rule follows Unsloth Studio's, with SurfSense's speed gate in place of its "does it load".

1. **The default, blind to hardware:** the first build whose quantization is in the preference order. The order starts with the quantizations that give the most quality per byte and ends with the unquantized ones:

   ```text
   UD-Q4_K_XL, UD-Q4_K_L, UD-Q5_K_XL, UD-Q3_K_XL, UD-Q6_K_XL, UD-Q8_K_XL, UD-Q2_K_XL,
   Q4_K_M, Q4_K_S, Q5_K_M, Q5_K_S, Q6_K, Q8_0, Q3_K_M, Q3_K_L, Q3_K_S, Q2_K,
   IQ4_NL, IQ4_XS, F16, BF16, F32
   ```

2. **The recommended build, for this machine:**
   - the default, when its speed tier is recommendable (`FULL` or `LIGHT_SPILL`, [`speed.py`](../../surfsense_local/backend/modules/llm/fit/speed.py));
   - else the largest build smaller than the default whose tier is recommendable, at four bits or more;
   - else none. The model gets no star, and every build physics does not refuse stays installable.

Rules:

- **Never above the default.** A build larger than the default is never recommended, however much memory is spare: on a large card, recommending the largest build that fits picks F16, several times the download for little gain.
- **The gate is the speed tier the badge reads.** Unsloth keeps the default whenever it loads at all, including a heavy CPU spill. Using `RECOMMENDABLE_TIERS` for both the default check and the step-down means a recommended build never carries a badge saying it will be slow.
- **Never below four bits.** A three or two bit build of a larger model is not clearly better than a four bit build of a smaller one, so past that floor the star moves to the smaller model. Those builds stay listed and installable; they are never recommended.
- **A build is priced at its whole footprint**, the weights plus its projector, at the cache precision the loader would choose. Priced on the weights alone, a vision build is recommended and then does not fit once its projector loads.
- **The builds' order in the manifest carries no preference.** The preference order picks the default and size orders the step-down, so the manifest stores builds smallest first, for readable diffs.

The two steps are pure functions over builds, not over manifest entries: `default_build(builds, preference)` and `recommended_build(builds, default, tier_of)`. A build supplies its quantization label and footprint, and `tier_of` is handed in, so a curated model passes its committed `shape` and a searched repo could pass its header's. Only curated models call them in this work.

The backend decides, the screen renders. A curated row carries every build with its fit and badge, the default's quantization, which build is recommended, and **the build it leads with and why**: `in_use`, then `installed`, then `recommended`, then `fits_slower` (the largest four bit or better build that installs, so a model with no recommendation still offers a build that installs rather than a refusal), then `nothing_fits` (the default, to say how big the model is). The row's Download fetches that build. The screen computes nothing, and curated rows sort by the fit of the build they lead with, then by list position.

**Badges are warnings.** A build that runs fully or spills a little (`FULL`, `LIGHT_SPILL`) carries no badge, only a quiet reason line; a heavier spill shows "Reduced speed" in amber and a refusal "Won't fit" in red. The tiers a build can be recommended at are exactly the tiers with no badge, so the star and a warning never share a row ([`fit.md`](../architecture/local-models/fit.md#badges)).

### Search

`catalog/local/search/` is the one live part of either catalog: 200,000 GGUF repos cannot be packaged. It is opt-in and asks egress consent for `huggingface.co`. Search results rank by downloads and are described, never judged: downloads, licence, gated, and Vision when the repo's file names include a projector, by the same projector rule `builds.py` uses; the listing's `full=true` already carries every repo's file names, so this costs no request. A hit also keeps its `base_model:quantized:` tag as `quantized_from`, returned by the API and not shown. Nothing from search is written to a manifest.

**Opening a repo reads its listing, never a file.** The repo summary and file tree come back in about a second; each build shows its exact size and a fit estimated from sizes, marked `~`, which over-charges on purpose (weights plus 15% and a gibibyte) so it never calls a spill resident, and never refuses. The type comes from the repo's tag and Hugging Face's parsed architecture, ignored when it names a projector, marked approximate. **Installing a build reads it exactly:** before any bytes move, the weights' and projector's headers are read, the build is refused if it is not a model, not a type the runtime runs, or too big, and a projector that does not see or belongs to another model is dropped. Reading a header costs about 50 ms because a vocabulary is counted, not decoded.

Opening a repo picks its builds with `catalog/local/builds.py`, the same file-picking rules the refresh script uses, so a searched repo and a curated one can never disagree about which file is the model and which is the projector. The builds are listed smallest first, each with its size and fit badge, and each shows the same install button and progress as a curated build. Search has no default build and no recommendation, of a build or of a model: SurfSense recommends only what a person curated and reviewed.

## Remote

### Classifier and support

`catalog/remote/classifier.py` and `catalog/remote/support.py` are the former `taxonomy/classify.py`, `taxonomy/supports.py` and `not_text_gen.py`, moved, with their tests, and reading the manifest's field names (`context` for `limit.context`) instead of a raw models.dev entry. Their rules do not change. An endpoint that declares `output_modalities` in its own listing is classified from those first, since the endpoint is the authority on what it serves.

### Catalog

`catalog/remote/catalog.py` is a pure function: the manifest and the user's connections with their listings in, rows out. It fetches nothing; connection discovery calls the endpoints and hands the results in.

| Situation | Rows from | Each row says |
|---|---|---|
| A manifest provider the user has not connected | manifest | "Add a key to use" |
| A manifest provider the user has connected | manifest, checked against the live listing | available, or not served by this connection (retired, or the key lacks access) |
| The same, listing failed | manifest | could not check |
| An id the listing has and its provider's manifest does not | the listing, classified by lookup | available; unknown when nothing matches |
| A custom endpoint (vLLM, a company gateway) | the listing only, each id classified by lookup | available; unknown when nothing matches |

For a connection to a manifest provider, the model is looked up under that provider only: OpenRouter's rows describe OpenRouter. An id with no provider to scope it, from a custom endpoint or new since the last refresh, is looked up across providers, in order:

1. **The maker's own entry**, when the id's prefix names a provider that carries it, under the id without the prefix or with it: `openai/gpt-5.5` reads OpenAI's `gpt-5.5`.
2. **The types every provider agrees on**: the intersection of what each provider carrying the id says, and support fields only where they all report the same value. Only 30 of 3,814 ids get a different type from different providers, mostly bare OpenAI ids one gateway extends with image output; the intersection labels `gpt-5` a text model rather than unknown, and never claims a type any provider disputes.
3. **Otherwise unknown**: nothing carries the id.

Each step tries the full id, then its last path segment, so `Qwen/Qwen3-8B` on a vLLM server finds the manifest's rows for it.

**A connection names its manifest provider.** The connection form's presets come from the manifest, and picking one stores its provider id on the connection; a typed URL stores `custom`. Stored, not inferred from the URL, because gateways and proxies make URLs unreliable.

**One row per provider and model.** `openai/gpt-5` and `openrouter/openai/gpt-5` are two rows, with their own classification, because a selection is a model on a connection, as it is today.

## Layout

```text
modules/llm/model_type.py  ModelType: the one primitive local, remote, selection and the database share
modules/llm/selectable.py  the one rule for which slots a model fills
modules/llm/catalog/
  source.py                Source: the catalog's source filter
  local/
    manifest/              models.json, schema, loader
    classifier.py          GGUF evidence → type
    support.py             context, reads images, tools
    catalog.py             manifest + downloaded files → rows
    recommendation.py      the model-level star: the first model with a recommended build
    lead_build.py          the build a row leads with, and why
    pricing.py             one price for a build: exact from a shape, else estimated from sizes
    downloaded.py          reads the models folder, cached on path, size and mtime
    installs.py            the install record: which files each install put on disk
    quantization.py        a build's quantization label, prefix kept
    builds.py              which files make a build, and the repo's projector: used by search and the refresh script
    build_choice/          which build of a model to recommend
      preference.py        the quantization preference order
      default_build.py     the first build in that order, blind to hardware
      recommended_build.py the default, or the largest smaller build fast enough here
    search/                hits.py, listing.py, repo_row.py, exact_check.py, tickets.py
    rows.py                the local row
    service.py             the side effects: the machine, the models folder, the network
    schemas.py             what the local routes return
    dependencies.py        wiring the service once per process
    router.py              the local routes, `/llm/system` and `/llm/install`
  remote/
    manifest/              models.json, schema, loader, lookup
    classifier.py          modalities → type, over a manifest entry
    support.py             tool call, reasoning, structured output, context
    not_text_gen.py        the names that refuse embedders and rerankers
    catalog.py             manifest + connections' listings → rows
    rows.py                the remote row, its availability, and the inputs catalog.py takes
    schemas.py             what the remote routes return
    router.py              the remote routes

scripts/refresh_remote_manifest.py   fetch, translate, guard, validate, write
scripts/remote_manifest/             translate.py, endpoints.py (the reviewed table), guard.py, render.py
scripts/refresh_local_manifest.py    read each repo at a pinned commit, assemble, guard, write
scripts/local_manifest/              entries.py (the hand-authored list), hub.py, assemble.py, guard.py, recorded.py
```

The remote router mounts under `/llm/catalog/remote`; the local one under `/llm`, where it serves `/llm/catalog/local`, `/llm/system` and `/llm/install`. Downloading, fit, hardware and the runtimes stay outside `catalog/`: they are about running a model, not knowing what it is. Connection CRUD, keys and live discovery stay in `connections/`: discovery calls a connection's `/models`, reads declared modalities first, and otherwise asks the manifest lookup, scoped by the connection's `catalog_provider`.

Adding a type is an enum value in `model_type.py`, the classifier groups that emit it, and a CHECK migration. Adding a remote provider is a manifest refresh. Adding a kind of source is a new side under `catalog/` with the same four files.

## HTTP

| Route | Returns | Network |
|---|---|---|
| `GET /llm/catalog/local` | manifest and downloaded rows, budget, `gpu_status` | none |
| `GET /llm/catalog/local/search?q=` | search hits | `host:huggingface.co` |
| `GET /llm/catalog/local/search/{repo}` | a repo's builds from its listing: exact sizes, estimated fit | `host:huggingface.co` |
| `POST /llm/install` | the install stream; a searched build's headers are read first | `host:huggingface.co` |
| `GET /llm/catalog/remote` | the providers: name, `connect`, and how many models of each type they serve | none |
| `GET /llm/catalog/remote/providers/{id}` | one provider's rows, connected ones marked unchecked | none |
| `GET /llm/catalog/remote/connections/{id}` | that connection's rows, checked against its listing | that host |

All 8,116 remote rows in one response would be several megabytes, one provider holding 586 of them, so the providers come first and a provider's rows when it is opened.

The screen paints local and remote rows from the two offline routes at once, then each connection's check fills in on its own, so a slow endpoint never holds the page. `/llm/image/local/*` and `/llm/connections/{id}/models` go in step 6, with the screen that replaces their readers.

## The screen

- One list, two filters: **Source** (All, Local, Remote) and **Capability** (each type that has rows, and Unknown when any row is).
- A local row keeps its badge (a warning only), Download, Use and Delete, and the recommendation mark, and shows **Vision** when `reads_images` is true, curated or not. The progress bar sits under the build being installed. A remote row shows its provider and connection, Test and Use, or Add a key.
- Hugging Face search is its own box, because it sends what the user types to a third party.
- Connections (URL, key) are managed in a settings panel, `features/connections/`. Their models appear in the catalog.

## Order of work

Each step ships alone and leaves the app working.

1. **Shared words.** `model_type.py` and `selectable.py`; `selected_models` keyed by `model_type`, with its migration; `/llm/selection/{model_type}`; selection and the pickers use the one rule. `source.py` waits for its first reader, in 3c.
2. **Remote manifest.** The refresh script keeps providers and evidence; the classifier and support move under `catalog/remote/` and run at lookup; connections read types from them. Embedders stop reading as chat. The `connect` block and `call` wait for step 3, which is their first reader.
3. **Remote catalog**, in four commits:
   - **3a.** `connect` and `call` in the manifest, and the reviewed table.
   - **3b.** A connection stores its manifest provider (`catalog_provider`, or `custom`), and the lookup is scoped by it.
   - **3c.** `catalog/source.py` and `catalog/remote/catalog.py`, the pure function from the manifest and the listings to rows.
   - **3d.** The three remote routes, and the connection form's presets from the manifest.
4. **Local classifier.** Replaces `not_chat.py`; downloaded files and search results classified; diffusion GGUFs become `IMAGE_GEN`, not runnable. Local selection reads `selectable_for` over the classifier's types, as remote does, and the llama.cpp provider stops declaring `completion` for every file on disk, which let a downloaded embedder fill the `text_gen` slot. `support.py` reads `reads_images` from a projector's header.
5. **Local manifest.** The new schema, `builds.py`, and the refresh script with its recorded-response tests and its guards; sd.cpp's models move in; the downloader fetches a build's file set, pinned by revision and verified by sha256, in one stream for text and image; each curated model recommends a build by its default and the step-down, priced at its whole footprint. The manifest's list is reversed once, from the old smallest first to most preferred first. The old `catalog/` root files move under `catalog/local/`, and the local routes move to `/llm/catalog/local`.
6. **The screen.** One list, both filters; connections become a settings panel. `/llm/connections/{id}/models` and `/llm/image/local/*` go with the cards and pickers that still read them.
7. **Searched image models.** Single-file SD 1.5 and SDXL from search become runnable.

## Decided here

- Two catalogs, one shared vocabulary.
- Manifests hold evidence, are refreshed by script and reviewed, and are never fetched at packaging.
- `ModelType` is a primitive of `modules/llm/`, and a type is a selection: no roles. Every type is listed and selectable, and one no feature reads yet says so.
- Remote providers are browsable before they are connected.
- A connection stores its manifest provider; a typed URL is `custom`.
- A remote model is identified by `provider/model`; no provider is excluded and no entries are merged.
- Every models.dev provider stays in the manifest. One the app cannot call is `unreachable` with its reason, not dropped.
- Deprecated models stay in the manifest, hidden by default.
- No price is shown.
- Image models get no fit estimate or recommendation mark in this work: their rows show the download size. sd.cpp's memory depends on the VAE, the text encoders and the output resolution, and `fit/` prices llama.cpp only. Deferred.
- This work stores and shows support, and sizes chat history from `context`; nothing else in chat changes. An agent loop, where chat hands the model tools such as document search and reads `tool_call` to know which models can take part, belongs to a later chat rework with its own proposal. Chat has no tools today ([`chat.md`](../architecture/chat.md)).
- A local model is a set of files with roles, each pinned to a commit and verified by sha256. A multi-file image model is runnable when the manifest lists its files; one found by search is classified and not runnable.
- Local text and image models share one manifest list and one classifier; `id` is ours, not a repo, and `aliases` name the other repos that hold the same model.
- A curated model pins every build in the quantization preference order. Its recommended build is the default when that runs at a recommendable speed, else the largest smaller build that does, never a larger one. The rule is two pure functions over builds; the backend computes it and the screen renders it.
- Only curated models are recommended, as a model or as a build. Search lists builds with their fit and recommends nothing.
- A recommendation never goes below four bits, and a row leads with the build its Download fetches, chosen and explained by the server.
- A badge is a warning: none where a build can be recommended, amber for a heavier spill, red for a refusal.
- Opening a searched repo reads no file; the exact header read happens at install, before any bytes move.
- A projector is paired with its model at install and recorded, never guessed from what sits in the folder.
- A local model reads images when its build carries a projector: listed in `files[]` for a curated build, read from the projector's header for any other. `reads_images` is a support badge, never a type, and every local row, curated or not, carries the same `LocalSupport`. Images are the only extra input shown; audio waits for a feature that sends it.
- Sending images to a local model in chat is chat's change, not this one.
- Sampling and image settings are per model, proposed by the script from published sources, reviewed, and recorded with their origin.
- Nothing about a local model is read from a filename except its quantization label, which keeps a quantizer's prefix such as `UD-`.
- The refresh script and search share one set of file-picking rules.
- From the references studied (Unsloth Studio, Local AI Zone, GGUF Loader), rules and conventions are borrowed and no code: Unsloth Studio is AGPL-3.0.

## Open questions

None.
