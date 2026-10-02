# Embedding model

Which model turns passages and questions into vectors. It is chosen once, in onboarding, and fixed for the whole library: every vector in it was made by that model, and changing it means embedding everything again, which is not built ([proposal](../proposals/embedding-model-change.md)).

**Code:** [`modules/embedding/`](../../surfsense_local/backend/modules/embedding/), [`engines/onnxruntime/`](../../surfsense_local/backend/modules/llm/catalog/local/engines/onnxruntime/), [`frontend/src/features/onboarding/model-step/use-embedding-step.ts`](../../surfsense_local/frontend/src/features/onboarding/model-step/kinds/use-embedding-step.ts), [`frontend/src/features/embedding/`](../../surfsense_local/frontend/src/features/embedding/)
**Decisions:** [ADR 0007](../adr/0007-bundled-embeddings.md), [ADR 0036](../adr/0036-the-index-records-its-embedder.md), [ADR 0037](../adr/0037-embedding-is-a-type-not-a-slot.md)

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

An int8 export of the same model (`model_quantized.onnx` from `Xenova/bge-small-en-v1.5`, 34.0 MB) is half the size and embeds chunk-sized text 1.6 times as fast on that machine, but it is not the same vector space: against the bundled file its vectors have a mean cosine of 0.998 and a minimum of 0.978 over the retrieval eval's 66 queries, and one of the eval's 66 queries changes rank by one place, both on a fresh index and when only the query side changes. The top-5 rate is 91% for both, which that eval cannot tell apart. Every library that embeds with bge-small was built with the bundled file, which is pinned by hash, so another build of it can replace it there only through a re-embed ([proposal](../proposals/embedding-model-change.md)).

## Hugging Face

`GET /embedding/huggingface/search?q=` lists repos tagged `sentence-similarity` or `feature-extraction`, most downloaded first. `GET /embedding/huggingface/repo/{repo}` opens one, without downloading weights, as a catalog row with one build, or none and why. Both answer in the GGUF search's shapes (`SearchRead`, `RepoRead`), so onboarding renders them through the same search as the chat step:

- **Checksums:** a small file Hugging Face keeps out of LFS, such as most `tokenizer.json` files, lists no sha256, so it is hashed from its bytes at the pinned commit.
- **Refused** when gated, when Hugging Face's own security scan flags a file it would take or anything as `unsafe`, when it has no ONNX build or no `tokenizer.json`, or when a weights file lists no checksum.
- **Which file:** a generic int8 build (`model_int8.onnx`, `model_quantized.onnx`), else full precision; never one tuned for a single CPU, an `O1`–`O4` variant, or an fp16, q4 or bnb4 build. External data downloads with it under its own name ([`pick.py`](../../surfsense_local/backend/modules/embedding/huggingface/pick.py)).
- **The spec** comes from the repo's sentence-transformers files: pooling, prompts for questions and passages, maximum length, capped at 2,048 tokens. Vectors are always normalised, since search compares by cosine. A repo with those files is `declared`; one with only the tag is `inferred` and takes bge's defaults. The ranking weight is 0.65, bge's, since nobody measured it ([`spec_from_repo.py`](../../surfsense_local/backend/modules/embedding/huggingface/spec_from_repo.py)).

An open repo is installed through the same install jobs as every local model, under the name `hf--<owner>--<name>`. After the download, two checks run before it can be chosen ([`verify.py`](../../surfsense_local/backend/modules/embedding/verify.py)):

1. **The probe** embeds one passage; its width is the one kept, over whatever the config said.
2. **The search check** asks ten questions over twenty passages, each answer beside a decoy on the same topic, and every answer must rank first ([`search_check.py`](../../surfsense_local/backend/modules/embedding/search_check.py)). bge-small and both curated granite models found 10 of 10; chat models served as embedders found 5 to 8, except one at 10. It shows a model can find answers, not that it was built to embed.

A model that fails is deleted and the install says why. One that passes keeps its settled spec beside its files and is listed as a downloaded row, labelled not tested by SurfSense.

## Known gaps

- A Hugging Face repo deleted or made private after it was chosen cannot be downloaded again; nothing can repair the library until changing the model is built.
- A remote embedder is not offered yet ([proposal](../proposals/embedding-model-choice.md)).
