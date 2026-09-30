---
status: proposed
code:
  - surfsense_local/backend/worker/ingestion/parsing.py
  - surfsense_local/backend/scripts/fetch_docling_models.py
  - surfsense_local/backend/pyproject.toml
---

# A GPU for the document parser

> Owns: whether Docling ingest uses a GPU, and through which runtime. Today it
> never does ([documents](../architecture/documents.md)). This proposal records
> the evidence so the choice is made once, with numbers, rather than by adding a
> wheel.

## Why the parser is on the CPU today

- `pyproject.toml` takes torch from PyPI. The Windows wheel is CPU-only
  (`2.14.0+cpu`), and Linux is pinned to the CPU index on purpose. Docling's
  `device="auto"` asks torch, finds no CUDA and picks `cpu`, even on an RTX card.
- [ADR 0012](../adr/0012-vulkan-only-gpu-backend.md) ships no CUDA payload, and
  the Windows installer must stay under makensis's 2 GB ceiling.
- The GPU is the chat model's. audio.cpp is pinned to the CPU for that reason,
  and nothing coordinates VRAM between `worker-ingest` and llama-server, whose
  fit reads live free memory ([fit](../architecture/local-models/fit.md)).

## Where the time goes on a CPU

Docling 2.125, Ryzen 7 5800X, with the parser settings from
[#2096](https://github.com/MODSetter/SurfSense/pull/2096):

- **First document of a session:** the import and model load, about 12 s from a
  warm disk cache and 34 s in the first frozen run we logged. This is not GPU work.
- **Per page, 8 threads, generated corpus:** 3.0 s born-digital, 5.2 s scanned,
  6.0 s photographed. Layout is about 0.7 to 1 s a page and TableFormer about
  2 s a table.
- **Scans and photos:** OCR dominates, and within it text recognition: 3.5 s of
  4.5 s on one full-page scan. The OCR stage is one thread and does not overlap
  pages.

So a GPU helps scans and table-heavy files. It does nothing for the first-job
wait.

## Options

| Route | Covers | Payload | For | Against |
|---|---|---|---|---|
| CUDA torch | NVIDIA | +1.9 to 2.6 GB (Windows `cu130`/`cu126` wheels) | Every Docling stage; Docling's published 3.5 to 5x on layout and tables with OCR off | Breaks ADR 0012 and the NSIS ceiling; NVIDIA only; silent CPU fallback when the driver is older than the wheel |
| `onnxruntime-gpu` | NVIDIA | +0.6 to 1 GB with cuDNN | OCR and an ONNX layout model | Same ADR conflict; RapidOCR's cuDNN default re-tunes per line shape and ran recognition 4 to 7x slower than CPU until it is set to `DEFAULT` |
| `onnxruntime-directml` | Windows: NVIDIA, AMD, Intel | about +11 MB over the CPU wheel; +171 MB for the heron ONNX layout model | Vendor-neutral, DX12 only; Docling already asks RapidOCR for DML | Maintenance mode; stuck at 1.24.4 while we run 1.29, and it replaces the `onnxruntime` package the embedder also uses; TableFormer stays on the CPU |
| ONNX Runtime WebGPU plugin | D3D12 or Vulkan, Metal | 5 to 13 MB | Closest match to ADR 0012: one package for every vendor | Needs a hook, since neither Docling's ONNX layout engine nor RapidOCR can register a plugin EP; open DETR-family bugs; unmeasured on heron and PP-OCR shapes |
| CoreML (macOS) | Apple Silicon | none, in the stock wheel | RapidOCR's `use_coreml` is reachable through `rapidocr_params` | CoreML EP was slower than CPU in RapidOCR's own test; layout already uses MPS |
| VLM through llama.cpp | every GPU the chat runtime sees | granite-docling 258M GGUF, about 133 MB | Uses the Vulkan runtime we already ship; the biggest accuracy lever on hard scans and forms | A second model resident beside chat; hallucination risk; only worth it for pages Docling scores low |

## Docling behaviour to know first

- Docling sets RapidOCR's per-stage `Det/Cls/Rec.use_dml` and `use_cuda` keys,
  but RapidOCR reads only `EngineConfig.onnxruntime.*`, so GPU OCR has to be
  asked for through `RapidOcrOptions.rapidocr_params`.
- The ONNX layout engine passes an explicit `providers` list straight to
  onnxruntime; its automatic mode only ever picks CUDA or CPU.
- Only the layout stage batches pages, so batch sizes do nothing on a CPU.

## Next step

Measure before choosing. On one NVIDIA, one AMD and one Intel machine, time
OCR and heron-onnx on DirectML and on the WebGPU plugin, with a chat model
loaded, against the CPU numbers above. Decide the VRAM rule in the same pass:
for example, the parser uses the GPU only while no chat model is resident.
