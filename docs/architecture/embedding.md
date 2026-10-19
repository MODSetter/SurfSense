# Embedding model

Which model turns passages and questions into vectors. It is chosen once, in onboarding, and fixed for the whole library: every vector in it was made by that model, and changing it means embedding everything again, which is not built ([proposal](../proposals/embedding-model-change.md)).

**Code:** [`modules/embedding/`](../../surfsense_local/backend/modules/embedding/), [`engines/onnxruntime/`](../../surfsense_local/backend/modules/llm/catalog/local/engines/onnxruntime/), [`frontend/src/features/onboarding/model-step/use-embedding-step.ts`](../../surfsense_local/frontend/src/features/onboarding/model-step/kinds/use-embedding-step.ts), [`frontend/src/features/embedding/`](../../surfsense_local/frontend/src/features/embedding/)
**Decisions:** [ADR 0007](../adr/0007-bundled-embeddings.md), [ADR 0036](../adr/0036-the-index-records-its-embedder.md), [ADR 0037](../adr/0037-embedding-is-a-type-not-a-slot.md), [ADR 0058](../adr/0058-the-bundled-embedder-runs-at-fp32-on-x86-64.md)

## The index

A row in `embedding_indexes` holds a snapshot of the model's spec and names its vector table ([data model](data-model.md)). Ingest and Studio write through it, search reads through it, and each document records which index it was embedded into ([documents](documents.md), [search](search.md)). Until onboarding finishes there is no row, and the routes that queue embedding work answer `409 embedding_not_chosen`.

## Choosing

Onboarding's last step lists the choices; finishing onboarding locks the one chosen ([selection](local-models/selection.md#onboarding)), and skipping means bge-small. Settings › Embedding shows it, its vector size, and whether SurfSense tested it, and offers no way to change it.

| Source | Where it comes from | Label |
|---|---|---|
| bge-small | bundled in the read-only models pack, pinned by hash | measured |
| curated | the local manifest, run by onnxruntime ([catalog](local-models/catalog.md)); ranking weight measured by the retrieval eval | measured |
| Hugging Face | any ONNX embedder, found by search | declared, or inferred |

The bundled bge-small is `model_optimized.onnx` from `Qdrant/bge-small-en-v1.5-onnx-Q`. The repo is named for quantization, but the file stores its 33.2 million weights as FLOAT16 and is 66,465,124 bytes (66.5 MB). Measured for [#1996](https://github.com/MODSetter/SurfSense/issues/1996) on an Apple M6 with onnxruntime 1.29.0's CPU provider at default threads, through the app's own recipe (the bundled tokenizer, truncation at 512 tokens, CLS pooling, normalised, batches of 32), it embeds about 72 short passages a second (a median of 53 tokens each) and about 14.5 chunk-sized ones (512 tokens each).

An int8 export of the same model (`model_quantized.onnx` from `Xenova/bge-small-en-v1.5`, 34.0 MB) is half the size and embeds chunk-sized text 1.6 times as fast on that machine, but it is not the same vector space: against the bundled file its vectors have a mean cosine of 0.997 and a minimum of 0.978 over the retrieval eval's 66 queries (0.998 and 0.992 over 119 short passages of its corpus), and one of those queries changes rank by one place, both on a fresh index and when only the query side changes. The top-5 rate is 91% for both, which that eval cannot tell apart. Every library that embeds with bge-small was built with the bundled file, which is pinned by hash, so another build of it can replace it there only through a re-embed ([proposal](../proposals/embedding-model-change.md)).

## Precision

On x86-64, onnxruntime's CPU provider runs the bundled file's FP16 MatMuls through a slow kernel, so there the encoder runs it upcast to FP32 ([ADR 0058](../adr/0058-the-bundled-embedder-runs-at-fp32-on-x86-64.md)). When the active spec is the bundled bge-small (same repo, revision and pinned weights) and the switch below says to, [`encoder.py`](../../surfsense_local/backend/modules/embedding/encoder.py) reads `model_optimized.onnx`, checks its sha256 against the pin, rewrites every FLOAT16 initializer, Constant tensor, Cast target and declared type as FLOAT in memory, and opens the session from those bytes. The rewrite is stdlib and numpy over the protobuf wire format, since the frozen app has no `onnx` package, and it refuses any part it cannot rewrite whole ([`fp32_upcast.py`](../../surfsense_local/backend/modules/embedding/fp32_upcast.py)). A hash mismatch, a refusal or an onnxruntime error logs one warning for that session load and opens the file as shipped. Nothing on disk changes, nor the index's recorded spec or its vector table: the pinned file still defines the vector space, and the runtime only executes it at higher precision.

`SURFSENSE_LOCAL_EMBED_PRECISION`, in any case ([`precision.py`](../../surfsense_local/backend/modules/embedding/precision.py)):

| Value | Does |
|---|---|
| `auto`, the default | upcasts on an x86-64 build, `sysconfig.get_platform()` ending in `amd64` or `x86_64`: the Windows and Linux x64 builds, and the Windows one under emulation on ARM, which `platform.machine()` reports as ARM64. macOS ships arm64 only and stays FP16 |
| `fp16` | the file as shipped, as before |
| `fp32` | upcasts on any architecture |
| anything else | logs a warning and means `fp16` |

Curated and Hugging Face embedders are never upcast, whatever the switch says.

Measured on a Ryzen 7 5800X under Windows with onnxruntime 1.29.0, through `embed()` in a fresh process for each precision, on 64 passages cut by the app's chunker (a mean of 345 tokens, batches of 32), with other work on the machine: 1.88 passages a second as shipped, 11.73 upcast, 6.2 times as fast. FP16 barely scales with threads: an earlier run found 1.86 a second at one thread and 2.04 at 8, against 4.01 and 11.6 upcast. At 4 threads the upcast was 4.1 times as fast, so a 4-core laptop should gain about that. The vectors differ only in their last digits, a cosine of at least 0.99999958 between the two, and the retrieval eval through the app's hybrid search, on a fresh index for each, put the answer at the same rank on all 266 queries (260 in the top 5 both ways).

Each process that embeds, `api`, `worker-ingest` and `worker-studio`, pays for it ([overview](overview.md#processes)):

- The first load takes 0.40 s instead of 0.18: reading 0.02 s, hashing 0.03 s, the rewrite 0.18 s and the session 0.15 s.
- Resident memory is 52 MB higher after the load (264 MB against 212) and 18 MB higher after embedding (1,180 against 1,162), and peaks 288 MB higher during the load (511 against 223).
- onnxruntime's wrapper keeps the model's bytes to rebuild the session on a provider fallback, which a CPU-only session never takes, so the encoder clears its private `InferenceSession._model_bytes`; holding them cost 126 MB. [`test_encoder_fp32.py`](../../surfsense_local/backend/tests/unit/embedding/test_encoder_fp32.py) fails when a session keeps any bytes, so an onnxruntime upgrade that renames it is caught, and the encoder logs a warning when the attribute is gone.

## Hugging Face

`GET /embedding/huggingface/search?q=` lists repos tagged `sentence-similarity` or `feature-extraction`, most downloaded first. `GET /embedding/huggingface/repo/{repo}` opens one, without downloading weights, as a catalog row with one build, or none and why. Both answer in the GGUF search's shapes (`SearchRead`, `RepoRead`), so onboarding renders them through the same search as the chat step:

- **Checksums:** a small file Hugging Face keeps out of LFS, such as most `tokenizer.json` files, lists no sha256, so it is hashed from its bytes at the pinned commit.
- **Refused** when gated, when Hugging Face's own security scan flags a file it would take or anything as `unsafe`, when it has no ONNX build or no `tokenizer.json`, or when a weights file lists no checksum. The first four carry a `NotAnEmbedderCode` (`repo_gated`, `repo_scan_flagged`, `repo_no_onnx`, `repo_no_tokenizer`) in the row's `not_runnable_code`, which the interface words in its own language ([localization](localization.md#backend-text)); the last names the file, so it travels as an English sentence with no code.
- **Which file:** a generic int8 build (`model_int8.onnx`, `model_quantized.onnx`), else full precision; never one tuned for a single CPU, an `O1`–`O4` variant, or an fp16, q4 or bnb4 build. External data downloads with it under its own name ([`pick.py`](../../surfsense_local/backend/modules/embedding/huggingface/pick.py)).
- **The spec** comes from the repo's sentence-transformers files: pooling, prompts for questions and passages, maximum length, capped at 2,048 tokens. Vectors are always normalised, since search compares by cosine. A repo with those files is `declared`; one with only the tag is `inferred` and takes bge's defaults. The ranking weight is 0.65, bge's, since nobody measured it ([`spec_from_repo.py`](../../surfsense_local/backend/modules/embedding/huggingface/spec_from_repo.py)).

An open repo is installed through the same install jobs as every local model, under the name `hf--<owner>--<name>`. After the download, two checks run before it can be chosen ([`verify.py`](../../surfsense_local/backend/modules/embedding/verify.py)):

1. **The probe** embeds one passage; its width is the one kept, over whatever the config said.
2. **The search check** asks ten questions over twenty passages, each answer beside a decoy on the same topic, and every answer must rank first ([`search_check.py`](../../surfsense_local/backend/modules/embedding/search_check.py)). bge-small and both curated granite models found 10 of 10; chat models served as embedders found 5 to 8, except one at 10. It shows a model can find answers, not that it was built to embed.

A model that fails is deleted and the install says why. One that passes keeps its settled spec beside its files and is listed as a downloaded row, labelled not tested by SurfSense.

## Known gaps

- A Hugging Face repo deleted or made private after it was chosen cannot be downloaded again; nothing can repair the library until changing the model is built.
- A remote embedder is not offered yet ([proposal](../proposals/embedding-model-choice.md)).
- The FP32 upcast is measured on one machine, a Ryzen 7 5800X under Windows. Linux x64, a 4-core laptop and the x64 build emulated on Windows on ARM are not measured.
- macOS runs the bundled file at FP16: the upcast has not been measured on Apple silicon.
