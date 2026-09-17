# Local model catalog expansion — cross-platform verification spec

## Background

`surfsense_local`'s "Local" model tab shows far fewer models than the hardware
scan (`llmfit`) actually finds. A model only survives into the catalog
(`recommended`/`explore`/`installed`) if `OllamaRuntime.resolve()` can build an
install plan for it, and today that requires `ScoredModel.ollama_name` to be
set — i.e. llmfit must know the model is already in Ollama's own registry
library.

Measured on this branch, on an Apple Silicon Mac (M2, 8GB unified memory), by
running the bundled `llmfit` binary directly with the exact invocation this
branch uses (`llmfit --max-context 8192 --json fit`, no result-count limit):

| Metric | Value |
|---|---|
| Total models scanned | 9,590 |
| Have `ollama_name` set | 138 (63 unique model families) |
| Usable today (`ollama_name` + fit Perfect/Good/Marginal) | 91 |
| Have `gguf_sources` (a Hugging Face GGUF repo) but no `ollama_name` | 1,508 |

The fix: `ScoredModel.gguf_sources` already carries a Hugging Face
`{provider, repo}` pointer for these models, and Ollama itself can pull any
GGUF straight from Hugging Face via `ollama pull hf.co/<repo>[:<quant>]` —
verified with a real pull/tags/show/delete round-trip against a local Ollama
instance (see "Already verified" below). So the plan is to synthesize a
`hf.co/<repo>` fallback `ollama_name` when llmfit doesn't give us a native one,
entirely within `_parse_model()` in
`surfsense_local/backend/modules/llm/recommendations/llmfit.py`. No new
runtime, no new binary — everything downstream (`OllamaRuntime`, `catalog.py`,
the frontend) already treats `ollama_name` as an opaque string.

## The open question this spec exists to answer

`ScoredModel.best_quant` — llmfit's own recommended quantization for a model —
is **not always a GGUF-compatible quant tag**. On the Mac used for the numbers
above, **100% of the 1,625 models with `gguf_sources` populated were scored
with `runtime: "MLX"`**, and `best_quant` for all of them was an MLX-specific
label (`mlx-4bit`, `mlx-8bit`) — not something you can pass to Ollama as a GGUF
file tag. This makes sense: MLX is Apple Silicon-exclusive (confirmed:
<https://github.com/ml-explore/mlx>), and llmfit is presumably recommending the
best *available* runtime for the machine it's running on — which on a Mac is
almost always MLX over llama.cpp.

**The question is what llmfit reports on Windows/Linux, where MLX isn't an
option at all.** The hypothesis is that llmfit should score most models
against `llama.cpp` there instead, and that `best_quant` in that case *should*
be a real GGUF tag (e.g. `Q4_K_M`, `Q5_K_M`, `IQ4_XS`) that's safe to append to
`hf.co/<repo>:<quant>`. This has **not been verified on real Windows/Linux
hardware** — everything above is Mac-only data. That's what this spec is for.

The planned code change (not yet written) will gate trust in `best_quant` on
`ScoredModel.runtime` normalizing to `"llamacpp"`:

```python
runtime = _code(row.get("runtime"))  # "llama.cpp" and "llamacpp" both -> "llamacpp"
trusted_quant = best_quant if runtime == "llamacpp" else None
```

If the hypothesis is right, GPU-equipped Windows/Linux machines get the full
benefit (a correctly-quantized pull *and* a fit score that actually matches
the file being downloaded), while Mac falls back to an untagged
`hf.co/<repo>` pull (Ollama's own default there is `Q4_K_M` when present,
confirmed empirically — see below) with the fit badge downgraded to
`UNKNOWN` for that row, since llmfit's `Perfect`/`Good`/`Marginal` numbers
would describe a different runtime's memory profile than what's actually
downloaded.

## Already verified (do not re-test these — just context)

- Real `gguf_sources` entries are dicts (`{"provider": "bartowski", "repo":
  "bartowski/..."}`), not strings — the current parser silently drops them all.
- `ollama pull hf.co/bartowski/SmolLM2-135M-Instruct-GGUF:Q4_K_M` against a
  local Ollama (v0.31.1) succeeded; `/api/tags` reported back the *exact same
  string*, `/api/show` returned a correctly auto-detected chat template, and
  `/api/delete` cleaned it up. No normalization/mangling of the identifier.
- Ollama's own no-tag default for `hf.co/...` pulls is "prefer `Q4_K_M` if
  present in the repo, else one reasonable quant" — not an arbitrary/huge file.
- FastAPI's `{model_name:path}` route (used for deleting local models)
  correctly round-trips a `%2F`/`%3A`-encoded `hf.co/...` identifier — tested
  with a minimal `TestClient` reproduction.
- `electron/scripts/fetch-ollama.mjs` and `fetch-llmfit.mjs` pin the identical
  version for every platform (`linux-x64`, `linux-arm64`, `darwin-x64`,
  `darwin-arm64`, `win32-x64`) — so any behavioral difference found below is a
  real hardware/OS/runtime-availability difference, not a version skew.

## What to run on Windows (and ideally Linux) with a GPU

### Test 1 — raw llmfit scan characteristics

From a checkout of this same branch:

```powershell
# Windows (PowerShell)
cd surfsense_local\electron\llmfit
.\llmfit.exe --max-context 8192 --json fit > fit_output.json
```

```bash
# Linux
cd surfsense_local/electron/llmfit
./llmfit --max-context 8192 --json fit > fit_output.json
```

Then run this analysis script (pure stdlib, works with any Python 3) against
the output:

```python
import json
from collections import Counter

d = json.load(open("fit_output.json"))
models = d.get("models", [])
total = len(models)

has_ollama = [m for m in models if m.get("ollama_name")]
has_gguf = [m for m in models if m.get("gguf_sources")]
gguf_only = [m for m in models if m.get("gguf_sources") and not m.get("ollama_name")]

print("=== Basic counts ===")
print("total scanned:", total)
print("has ollama_name:", len(has_ollama))
print("has gguf_sources:", len(has_gguf))
print("gguf_sources only (net new if fallback ships):", len(gguf_only))

print()
print("=== THE KEY QUESTION: runtime breakdown ===")
print("runtime values across ALL scanned models:", Counter(m.get("runtime") for m in models))
print()
print("runtime values for the gguf_sources-only group specifically:")
print(Counter(m.get("runtime") for m in gguf_only))

print()
print("=== best_quant samples, grouped by runtime, for the gguf_sources-only group ===")
for runtime in sorted(set(m.get("runtime") for m in gguf_only)):
    sample = [m.get("best_quant") for m in gguf_only if m.get("runtime") == runtime][:10]
    print(f"  {runtime!r} -> {sample}")

print()
print("=== Does a normalized 'llamacpp' runtime ever appear, and are its best_quant values GGUF-shaped? ===")
import re
def normalize(value):
    if not isinstance(value, str):
        return None
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

llamacpp_rows = [m for m in gguf_only if normalize(m.get("runtime")) == "llamacpp"]
print("gguf_sources-only rows with runtime normalizing to 'llamacpp':", len(llamacpp_rows))
print("their best_quant values:", Counter(m.get("best_quant") for m in llamacpp_rows).most_common(20))

print()
print("=== Usable (Perfect/Good/Marginal) counts ===")
def usable(m):
    return m.get("fit_level") in ("Perfect", "Good", "Marginal")
print("usable today (ollama_name only):", len([m for m in has_ollama if usable(m)]))
print("usable with fallback added (either source):", len([m for m in models if (m.get("ollama_name") or m.get("gguf_sources")) and usable(m)]))
print("usable AND has a trustworthy (llamacpp) quant in the gguf-only group:", len([m for m in llamacpp_rows if usable(m)]))
```

### Test 2 — Ollama `hf.co` pull round-trip (confirm it matches the Mac result)

Make sure Ollama is running (`ollama serve`, or however SurfSense's bundled
sidecar starts it), then:

```bash
# Pull a small model directly from Hugging Face
curl -s -N -X POST http://127.0.0.1:11434/api/pull \
  -d '{"model": "hf.co/bartowski/SmolLM2-135M-Instruct-GGUF:Q4_K_M", "stream": true}'

# Confirm the tag comes back byte-for-byte identical
curl -s http://127.0.0.1:11434/api/tags

# Confirm the chat template was auto-detected
curl -s -X POST http://127.0.0.1:11434/api/show \
  -d '{"model": "hf.co/bartowski/SmolLM2-135M-Instruct-GGUF:Q4_K_M"}'

# Clean up
curl -s -X DELETE http://127.0.0.1:11434/api/delete \
  -d '{"model": "hf.co/bartowski/SmolLM2-135M-Instruct-GGUF:Q4_K_M"}'
```

(On Windows, `curl` ships built-in on Windows 10 1803+ / Windows 11 as
`curl.exe`; the commands above work as-is from PowerShell or cmd.)

## What to paste back here

1. The full stdout of the Test 1 analysis script.
2. The four JSON responses from Test 2 (pull's final `{"status":"success"}`
   line, the `/api/tags` entry for the model, the `/api/show` `template`
   field, and confirmation the delete succeeded).
3. The GPU/OS details of the machine it ran on (GPU model + VRAM, OS version)
   — grab this from the `"system"` key in `fit_output.json` rather than typing
   it manually, so it's exact.

## Decision this informs

- If Test 1 shows `llamacpp`-normalized `runtime` values with GGUF-shaped
  `best_quant` strings (e.g. `Q4_K_M`) on GPU Windows/Linux hardware: ship the
  runtime-gated `trusted_quant` design above as planned — full fit-scoring and
  correct quantization for this group on such machines, degraded (untagged,
  `fit: UNKNOWN`) only on Mac.
- If it instead shows something unexpected (e.g. `llama.cpp` present but
  `best_quant` still not GGUF-shaped, or GPU machines also skew toward some
  other non-GGUF runtime for most models) — the gating condition needs
  rethinking before this ships, and this doc should be updated with whatever
  the real pattern turns out to be.
