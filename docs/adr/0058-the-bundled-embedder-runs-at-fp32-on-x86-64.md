# ADR 0058: The bundled embedder runs at FP32 on x86-64, upcast in memory, and its vector space is still the pinned FP16 file

- **Status:** Accepted
- **Date:** 2026-10-16
- **Amends:** [ADR 0036](0036-the-index-records-its-embedder.md): its consequence that the bundled file's "FP16 weights stay" now holds for the file on disk and what the index records, not for the precision onnxruntime computes in, which on x86-64 is FP32
- **Source:** measured on a Ryzen 7 5800X under Windows with onnxruntime 1.29.0, recorded in [embedding](../architecture/embedding.md#precision)

## Context

ADR 0036 pins the bundled bge-small file, `model_optimized.onnx`, by its sha256 and records it in every index's spec, so the file can never change without a re-embed. It stores its weights as FLOAT16. On x86-64, onnxruntime's CPU provider runs its 36 MatMuls in FP16 through a slow kernel, 83% of kernel time on a batch: it embedded 2.04 chunk-sized passages a second at 8 threads and 1.86 at one. No session option, optimisation level or config key in onnxruntime 1.29 changes that kernel. The same weights at FP32 ran 11.6 a second.

Every FP16 value is exactly an FP32 value, so upcasting the weights changes none of them; only the arithmetic becomes more precise.

## Decision

- On an x86-64 build, `sysconfig.get_platform()` ending in `amd64` or `x86_64`, the encoder reads the bundled file, checks its sha256 against the pin, rewrites every FLOAT16 initializer, Constant tensor, Cast target and declared type as FLOAT in memory, and opens the session from those bytes ([`encoder.py`](../../surfsense_local/backend/modules/embedding/encoder.py)).
- Nothing on disk changes: not the pack, the pin in [`bundled.py`](../../surfsense_local/backend/modules/embedding/bundled.py), `fetch_embedding_model.py`, migration `0022`, the index's recorded spec or its vector table. The pinned file still defines the vector space; the runtime executes it at higher precision, which the index does not record.
- Only the bundled file is upcast, matched by repo, revision and pinned weights. Curated and Hugging Face embedders run as downloaded, since their FP16 builds were never measured upcast.
- The rewrite is stdlib and numpy over the protobuf wire format ([`fp32_upcast.py`](../../surfsense_local/backend/modules/embedding/fp32_upcast.py)), because the frozen app has no `onnx` package. It refuses what it cannot rewrite whole, such as a subgraph, a sparse or external tensor, or an FP16 type attribute other than Cast's `to`. A hash mismatch, a refusal or an onnxruntime error logs one warning and opens the file as shipped.
- `SURFSENSE_LOCAL_EMBED_PRECISION` is the escape hatch: `auto` by default, `fp16` for the file as shipped, `fp32` to upcast on any architecture. A value it cannot read means `fp16`.
- arm64 stays FP16 until the upcast is measured there. Apple silicon already runs the FP16 file at 14.5 chunk-sized passages a second.
- **Rejected: shipping an FP32 file.** It adds 2.0 MB to the installer under LZMA but 66 MB installed, needs a second pinned hash, and every existing index records the FP16 file's hash, so it would also need a decision on whether the recorded spec changes. It can come with the next change to the pack.
- **Rejected: adding the `onnx` package** to convert at load. The wire rewrite adds no dependency, and its model's output is bit-identical to an `onnx`-converted file's.

## Consequences

- Embedding on x86-64 is 5.7 times as fast at 8 threads (2.04 to 11.6 passages a second; 6.2 times through the shipped encoder), 4.1 times at 4 threads and 2.2 times at 1. On the ingest research's A/B set of 6 documents, it alone cut the time to ingest them by 27%, from 500.6 s to 364.6 s.
- Vectors barely move: cosine at least 0.99999958 against the FP16 run, and the retrieval eval's answer at the same rank on 266 of 266 queries. Nothing is re-embedded; a library built at FP16 keeps its vectors, and what x86-64 embeds later sits beside them.
- Each process that embeds (`api`, `worker-ingest`, `worker-studio`) loads the model about 0.22 s slower once, holds about 52 MB more after the load, and peaks about 290 MB higher while it loads.
- The encoder clears onnxruntime's private `InferenceSession._model_bytes`, which would hold another 126 MB, so an onnxruntime upgrade is checked against a unit test that fails if the session keeps the bytes.
- If the pinned file ever changes, its upcast is measured again before it ships.

## Where the code stands

- Measured on one machine. Linux x64, a 4-core laptop, and the x64 build under emulation on Windows on ARM, which `auto` upcasts by its build, are not measured.
