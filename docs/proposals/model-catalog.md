---
status: proposed
code:
  - surfsense_local/backend/modules/llm/catalog/
  - surfsense_local/backend/scripts/
  - surfsense_local/frontend/src/features/model-catalog/
  - surfsense_local/frontend/src/features/connections/
---

# The model catalog

> Every model the app can use is classified from a packaged manifest, offline, and shown in one screen filtered by source (local, remote) and by capability (text, image). Local and remote are two catalogs that share one vocabulary and nothing else.

This reworks the local catalog ([`catalog.md`](../architecture/local-models/catalog.md)), the hard-coded sd.cpp list, and the per-connection model lists ([`connections.md`](../architecture/connections.md)). Those docs describe the code being replaced. They constrain this design only where a decision below says so.

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

**Why two catalogs.** Local and remote share almost nothing: a local model is a repo and a file, is priced for this machine and is downloaded; a remote model is a connection and an id, needs a key and is tested. One generalised shape over both is where maintenance and debugging break. They share only the words the screen filters on.

**Why a packaged manifest.** Listing and classifying never need the network. The catalog renders on first paint, on an airgapped machine, and every classification rule is a unit test over a committed fixture.

## The shared vocabulary

`catalog/types.py` is the only module both sides import:

```python
class Source(StrEnum):
    LOCAL = "local"
    REMOTE = "remote"

class ModelType(StrEnum):          # what a model is for: the capability filter
    TEXT_GEN = "text_gen"
    IMAGE_GEN = "image_gen"
    IMAGE_EDIT = "image_edit"
    VIDEO_GEN = "video_gen"
    AUDIO_GEN = "audio_gen"
```

- **A type is a filter, a support is a badge.** "Reads images" does not make a model an image model. Each side's support is its own dataclass, because the fields each can know differ.
- **None is not no.** A support field is `None` when the evidence is silent, as [`supports.py`](../../surfsense_local/backend/modules/llm/taxonomy/supports.py) already holds for models.dev.
- **Unknown is a state, not a type.** A remote id nothing recognises has no types and `known=False`. The capability filter offers "Unknown" only when such rows exist.
- **One word per idea.** `completion`, `image_generation` as a capability, and the curated `vision` go.

### Types and roles

The app has two roles, `generation` and `image_generation`. `catalog/roles.py` holds the one mapping:

```python
ROLE_FOR_TYPE = {
    ModelType.TEXT_GEN: ModelRole.GENERATION,
    ModelType.IMAGE_GEN: ModelRole.IMAGE_GENERATION,
}
```

Both catalogs list only rows with a type in that mapping, and the filter offers only those types. `IMAGE_EDIT`, `VIDEO_GEN` and `AUDIO_GEN` are still classified, because the classifier states what is true, and a new role unlocks its models with one line here. Selection and the chat and image pickers apply the same mapping, so a model is selectable for a role everywhere or nowhere.

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

      "builds": [                               // best quality first; the recommendation steps down
        {
          "quantization": "UD-Q4_K_XL",
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
          ],
          "run": { "args": [] },
          "validated": { "llama_cpp": null }    // the runtime build a person ran it on
        },
        { "quantization": "Q4_K_M", "…": "…" },
        { "quantization": "Q3_K_M", "…": "…" }
      ]
    }
  ]
}
```

| Part | Reliability | Experience |
|---|---|---|
| `evidence` | one classifier for everything local: a manifest entry, a downloaded file's header and a search hit all produce this same object | the capability filter |
| `aliases` | a file the user downloaded from another repo holding the same model, such as the vendor's or another quantizer's, is recognised as this entry | a searched download of a curated model shows as that model |
| `context`, `template` | chat sizes its history to the real window; the tool and reasoning flags are there for the later chat rework | badges such as "Reads images" and long context |
| `sampling` | each model runs with its publisher's settings, and a hybrid model with the right ones for each mode, not one set for every model | better answers with no settings to learn |
| `image` | Studio generates with the model's native size, steps, guidance and sampler | sensible defaults per image model |
| `shape` | the fit estimate and the recommendation, offline | Fits, Reduced speed, Won't fit |
| several `builds` | a machine that cannot fit the preferred build gets a smaller build of the same model before a smaller model | the best quality this machine can run |
| `files[]` and `role` | a model is a set of files: vision needs a projector, a multi-token-prediction model a drafter, FLUX a VAE and text encoders, a split build every part. The downloader fetches the set, and whether the app can run a model is whether its runtime supports every role | vision and image models work after download; a multi-file model is a manifest entry, not new code |
| `revision`, `upstream_repo` | a quantizer re-uploading, renaming or deleting a file cannot change what is downloaded; a mirror names what it copies | no failed download on a model that worked last month |
| `sha256`, `size_bytes` | every download is verified | an honest progress bar and a real verification step |
| `run.args` | launch flags are tested and committed, not hard-coded per model | image models that do not run out of memory while decoding |
| `license`, `publisher`, `source_repo` | nothing curated needs a Hugging Face account | who made it, under which licence, and where to read more |
| position, `validated` | the recommendation reads position; `validated` names the runtime build a person ran this exact build on, because some quantizations run only on newer or forked llama.cpp | "Recommended for this computer" |

- **`id` is ours**, not a Hugging Face repo: a build comes from a quantizer's repo, and an image model's files from several.
- **Every file is pinned to a commit.** Quantizers change repos in place: Unsloth renamed, moved and deleted files on `main` of a published repo, and re-uploads fixed chat templates under the same name.
- **`template` is read at refresh time** from the chat template in the header, so the catalog never loads a model to say what it supports.
- **Nothing is taken from a filename.** Not size, not parameter count, not quantization: a catalog that did so got 99.6% of its sizes wrong, and a quantizer names some files after a quantization they are not.

The three image models hard-coded in `providers/sdcpp/` become entries like any other.

### The curation path

`scripts/refresh_local_manifest.py`, run by hand, output reviewed in a pull request. Six steps, each owned by a person or the script:

1. **A person chooses the models.** Their order, `name`, `description`, `aliases`, and which repo each build comes from, preferring an ungated mirror of a gated vendor repo and recording the vendor as `upstream_repo`.
2. **The script resolves builds.** For each model it pins a few quantizations by a preference order (`UD-Q4_K_XL`, `Q4_K_M`, `Q3_K_M`, …, `F16` last), using the same file-picking rules search uses (`catalog/local/builds.py`): skip imatrix files and big-endian builds; take the first shard of a split set and list every part; look in quantization subfolders only when the repo root has none; attach a projector confirmed by its header (`general.type` is `mmproj`), preferring F16, and a multi-token-prediction file as a `drafter`.
3. **The script reads evidence** from each chosen file's own header over HTTP range requests, never from the repo-level `gguf` metadata Hugging Face serves, which describes one arbitrary file in the repo. `revision`, `size_bytes` and `sha256` come from the repo's file listing (`lfs.oid`) at a pinned commit. No weights are downloaded.
4. **The script proposes run defaults; a person reviews them.** Sampling comes from the repo's machine-readable `params` file where one exists, with its source in `origin`, because published settings disagree with each other between a model card, its docs and its example commands. Image settings are proposed per family and reviewed the same way.
5. **The script guards itself.** It refuses to write a build it could not read completely, so nothing unknown can be recommended; refuses a refresh that drops models or builds without the person naming them; and flags a chat template that differs between the pinned revision and `main`, which is how a quantizer ships a fix.
6. **A person validates.** Downloading a build, chatting with it and confirming citations resolve sets `validated.llama_cpp` to the runtime build it ran on.

The script is tested against recorded Hugging Face responses, so a change in how it reads a listing is caught in a test rather than in a shipped manifest.

### Remote

`catalog/remote/manifest/models.json`, built by `scripts/refresh_remote_manifest.py`, which grows out of today's `fetch_model_capabilities.py`. It keeps models.dev's nesting, provider then models, in the app's own words: models.dev is written for the Vercel AI SDK, and its `npm` and `env` fields name JavaScript packages and environment variables this app never uses. The script translates them into what the app does with a provider.

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
        "status": "ready",              // ready | needs_account_details | unreachable
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
| Call | `call` | a model served only on `/responses` (34 today) or through another protocol is unreachable with a reason, not a failure on the first message | the reason on the row |
| Display | `name`, `family`, `description`, `release_date`, `status` | | readable names, grouping by family, newest first, deprecated hidden by default and still named on a selection that uses one |

**How `connect` is derived.** models.dev writes a base URL (`api`) only for providers reached through the generic `@ai-sdk/openai-compatible` package; a provider with its own package has the URL built into that package. So:

| Case | Evidence | `connect` |
|---|---|---|
| URL stated | `api`, 197 of 223 providers | `ready`, `base_url_origin: models.dev` |
| URL is a template | `${VAR}` in `api` (Databricks, Cloudflare Workers AI, Infomaniak and two more) | `needs_account_details`, `account_fields` from the variables |
| No URL, one fixed endpoint | own SDK, OpenAI-compatible endpoint known (OpenAI, Groq, Mistral, xAI, Together, Cerebras, DeepInfra, Perplexity, Gemini, Anthropic) | `ready` from the reviewed table, `base_url_origin: reviewed` |
| No URL, per account | Azure, Cloudflare AI Gateway, SAP AI Core, watsonx and similar | `needs_account_details`, URL template from the reviewed table |
| Not a bearer key | Amazon Bedrock (AWS signing), Google Vertex (Cloud OAuth) | `unreachable`, with the reason |
| Loopback URL | LM Studio and three more | `key: none`, `local: true` |

`npm` is not a reachability test on its own: Groq, Mistral, xAI and Together have their own package and serve the OpenAI API. The reviewed table is where a person decides it, once per provider, in a pull request.

**Left out:** `cost`, because a list price refreshed a few times a year is wrong more often than it helps, differs from what a user with discounts, caching or a free tier pays, and billing is out of scope; the provider's `doc` link is on the row instead. `npm` and `env` are translated, not copied. `attachment` repeats the input modalities. `knowledge`, `interleaved` and `open_weights` have no reader. At this shape the file is about 3 MB, most of it `description`.

**A remote model's identity is `provider/model`.** `openai/gpt-5-nano` and `openrouter/qwen/qwen3.7-max`. The same model id appears under many providers (1,114 of 3,814 ids), and each provider's entry describes what that provider serves, which differs for 407 of them: `deepseek/deepseek-v3.2` takes PDFs on one provider and text only on nine others. Keyed by provider, nothing collides and nothing is merged. OpenRouter is one provider among the others, not an exclusion.

Today's snapshot drops the provider and keys by model id alone. That is what forced it to merge disagreeing entries by majority, to exclude OpenRouter, and to store two derived strings instead of the evidence, which is why embedders read as chat models.

## Local

### Classifier

`catalog/local/classifier.py`: an `evidence` object in, a type or known-none out. The manifest stores that object; for a downloaded file it is read from the header, and for a search hit from the candidate build's header and the repo's tag. It replaces the denylist in `catalog/search/not_chat.py`, which answered only "chat or refuse", with groups that each answer a type:

- Diffusion architectures (`sd1`, `sdxl`, `sd3`, `flux`, `flux2`, `qwen_image`, `z_image`, `lumina2` and the rest) are `IMAGE_GEN`. They were refused because the old catalog was text only; the app ships sd.cpp.
- Video architectures (`wan`, `ltxv`, `hyvid`, `cosmos`) are `VIDEO_GEN`, classified and not listed.
- Embedders, speech, labellers, OCR, draft heads and projectors are known-none.
- Any other architecture is `TEXT_GEN`. A denylist ages the right way: an unknown architecture is usually a chat model released last week.

Evidence rules:

- **The chosen file's own header**, never the repo name and never the repo-level `gguf` metadata, which describes one arbitrary file in the repo.
- **No single field decides.** The architecture alone misleads: a text-to-speech model declares `llama`, a speech recogniser `qwen3`, and embedders and rerankers declare chat architectures. The pipeline tag alone misleads too: it is often missing, including on repos that ship a projector. The groups key on both, and the tag only ever refuses or refines, never admits.
- **A projector is known by its header**: `general.type` is `mmproj`, and `clip.has_vision_encoder` and `clip.has_audio_encoder` say which inputs it serves. That is how a downloaded model with no manifest entry gets "reads images".
- **An unreadable header fails open to `TEXT_GEN`**, marked approximate, because refusing on a failed read hides models the user can run.

### What a type is, and whether the app can run it

Two answers the old code gave as one refusal. The classifier says a FLUX GGUF is `IMAGE_GEN`. The catalog says whether this app can run it: a model is runnable when its runtime supports every file role it needs and the app knows every file. A curated FLUX entry lists its VAE and text encoders and is runnable. A FLUX build found by search is one file with no known companions, so its row is `IMAGE_GEN`, not runnable, "Needs files SurfSense cannot find on its own".

### Catalog

`catalog/local/catalog.py` is a pure function: the manifest and the list of downloaded files in, rows out.

| Input | What it is | Network |
|---|---|---|
| Manifest | the models we picked, packaged | none |
| Downloaded files | what the user already downloaded into the models folder: from the manifest, from search, or copied there by hand | none |

Nothing is pre-installed; the app ships no model weights. A downloaded file is an input because its row offers Use and Delete instead of Download. A file whose repo is a manifest entry's `aliases` is shown as that entry. Any other, downloaded from search or copied by hand, is in no manifest: its own header is the only evidence, and the same classifier reads it. Header reads are cached on path, size and modification time, so a folder of large files is read once.

**The recommendation** walks the manifest from the most preferred model down. For each model it takes the best build this machine runs at a recommendable speed, stepping down that model's builds before moving to a smaller model, so a machine one gigabyte short of `UD-Q4_K_XL` gets the same model at `Q4_K_M` rather than a model half its size.

### Search

`catalog/local/search/` is the one live part of either catalog: 200,000 GGUF repos cannot be packaged. It is opt-in, asks egress consent for `huggingface.co`, and classifies a result with the same classifier over the candidate build's header. Search results rank by downloads and are described, never judged, as today.

Opening a repo picks its builds with `catalog/local/builds.py`, the same file-picking rules and quantization order the refresh script uses, so a searched repo and a curated one can never disagree about which file is the model, which is the projector, and which build to offer first.

## Remote

### Classifier and support

`catalog/remote/classifier.py` and `catalog/remote/support.py` are today's [`classify.py`](../../surfsense_local/backend/modules/llm/taxonomy/classify.py), [`supports.py`](../../surfsense_local/backend/modules/llm/taxonomy/supports.py) and `not_text_gen.py`, moved, with their tests, and reading the manifest's field names (`context` for `limit.context`) instead of a raw models.dev entry. Their rules do not change. An endpoint that declares `output_modalities` in its own listing is classified from those first, since the endpoint is the authority on what it serves.

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

1. **The maker's own entry**, when the id's prefix names a provider that carries it: `deepseek/deepseek-v3.2` reads DeepSeek's.
2. **Agreement**: every provider carrying the id classifies it the same way.
3. **Otherwise unknown**, never a majority vote.

Each step tries the full id, then its last path segment, so `Qwen/Qwen3-8B` on a vLLM server finds the manifest's rows for it.

**A connection names its manifest provider.** The connection form's presets come from the manifest, and picking one stores its provider id on the connection; a typed URL stores `custom`. Stored, not inferred from the URL, because gateways and proxies make URLs unreliable.

**One row per provider and model.** `openai/gpt-5` and `openrouter/openai/gpt-5` are two rows, with their own classification, because a selection is a model on a connection, as it is today.

## Layout

```text
modules/llm/catalog/
  types.py                 Source, ModelType: the only shared words
  roles.py                 ROLE_FOR_TYPE
  router.py                mounts both sides
  local/
    manifest/              models.json, schema, loader
    classifier.py          GGUF evidence → type
    support.py             context, reads images, tools
    catalog.py             manifest + downloaded files → rows
    downloaded.py          reads the models folder, cached on path, size and mtime
    builds.py              which files make a build, and the quantization order: used by search and the refresh script
    search/                Hugging Face search, tickets
    rows.py                the local row
  remote/
    manifest/              models.json, schema, loader, lookup
    classifier.py
    support.py
    catalog.py             manifest + connections' listings → rows
    discovery.py           calls a connection's /models
    rows.py                the remote row
```

Downloading, fit, hardware and the runtimes stay outside `catalog/`: they are about running a model, not knowing what it is. Connection CRUD and keys stay in `connections/`.

Adding a local type is a group in the local classifier and a line in `roles.py`. Adding a remote provider is a manifest refresh. Adding a kind of source is a new side under `catalog/` with the same four files.

## HTTP

| Route | Returns | Network |
|---|---|---|
| `GET /llm/catalog/local` | manifest and downloaded rows, budget, `gpu_status` | none |
| `GET /llm/catalog/local/search?q=` | search hits | `host:huggingface.co` |
| `GET /llm/catalog/local/search/{repo}` | a repo's builds, classified and priced | `host:huggingface.co` |
| `GET /llm/catalog/remote` | manifest rows, connected ones marked unchecked | none |
| `GET /llm/catalog/remote/connections/{id}` | that connection's rows, checked against its listing | that host |

The screen paints local and remote rows from the two offline routes at once, then each connection's check fills in on its own, so a slow endpoint never holds the page. `/llm/image/local/*` and `/llm/connections/{id}/models` go.

## The screen

- One list, two filters: **Source** (All, Local, Remote) and **Capability** (Text, Image, and Unknown when any row is).
- A local row keeps its fit badge, Download, Use and Delete, and the recommendation mark. A remote row shows its provider and connection, Test and Use, or Add a key.
- Hugging Face search is its own box, because it sends what the user types to a third party.
- Connections (URL, key) are managed in a settings panel, `features/connections/`. Their models appear in the catalog.

## Order of work

Each step ships alone and leaves the app working.

1. **Shared words.** `types.py` and `roles.py`; selection and the pickers use `roles.py`.
2. **Remote manifest.** The refresh script keeps providers and evidence; the classifier and support move under `catalog/remote/` and run at lookup; connections read types from them. Embedders stop reading as chat.
3. **Remote catalog.** `catalog.py`, the provider id on a connection, presets from the manifest, the two remote routes.
4. **Local classifier.** Replaces `not_chat.py`; downloaded files and search results classified; diffusion GGUFs become `IMAGE_GEN`, not runnable.
5. **Local manifest.** The new schema, `builds.py`, and the refresh script with its recorded-response tests and its guards; sd.cpp's models move in; the downloader fetches a build's file set, pinned by revision and verified by sha256, in one stream for text and image; the recommendation steps down builds before models.
6. **The screen.** One list, both filters; connections become a settings panel.
7. **Searched image models.** Single-file SD 1.5 and SDXL from search become runnable.

## Decided here

- Two catalogs, one shared vocabulary.
- Manifests hold evidence, are refreshed by script and reviewed, and are never fetched at packaging.
- Types with no role are classified and not listed.
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
- A curated model pins a few builds; the recommendation steps down a model's builds before moving to a smaller model.
- Sampling and image settings are per model, proposed by the script from published sources, reviewed, and recorded with their origin.
- Nothing about a local model is read from a filename.
- The refresh script and search share one set of file-picking rules.
- From the references studied (Unsloth Studio, Local AI Zone, GGUF Loader), rules and conventions are borrowed and no code: Unsloth Studio is AGPL-3.0.

## Open questions

None.
