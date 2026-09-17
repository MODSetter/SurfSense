# API — Phase 5d: llmfit model catalog expansion (cross-platform verification)

> Extends [`05a-model-recommendations.md`](05a-model-recommendations.md).
> Owns the `hf.co/<repo>` fallback `ollama_name` synthesis in
> `backend/modules/llm/recommendations/llmfit.py`'s `_parse_model()`.

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

The planned code change — **since shipped; see "Shipped" at the end of this
document for what landed and how it differs** — gates trust in `best_quant` on
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

### Test 3 — real inference + GPU offload (new)

Tests 1 and 2 confirm the model downloads and gets a template, but never
confirm it actually **generates coherent output** or that the GPU gets used.
Since the whole point is "best results for custom-built GPU PCs," this needs
its own check. Pull one of the actual newly-unlocked models from your own
Test 1 scan (the `typhoon-ai/llama3.2-typhoon2-3b-instruct` sample works
well, or pick any other `gguf_sources`-only entry from `fit_output.json`):

```bash
curl -s -N -X POST http://127.0.0.1:11434/api/pull \
  -d '{"model": "hf.co/mradermacher/llama3.2-typhoon2-3b-instruct-GGUF:Q8_0", "stream": true}'

curl -s http://127.0.0.1:11434/api/chat -d '{
  "model": "hf.co/mradermacher/llama3.2-typhoon2-3b-instruct-GGUF:Q8_0",
  "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
  "stream": false
}'

ollama ps
```

Check: is the `api/chat` response coherent, correctly-formatted prose (not
garbled — garbling would mean the auto-detected template is actually wrong
despite `/api/show` reporting one)? And does `ollama ps`'s `PROCESSOR` column
show GPU usage (e.g. `100% GPU`), not a silent CPU fallback?

### Test 4 — end-to-end catalog loop (new)

Tests so far only exercise Ollama's API in isolation. The actual point of
this fix is that a pulled model shows up correctly in SurfSense's own
"Installed" section on a later scan — i.e. that `catalog.py`'s
`installed_by_key` matching (keyed on the exact `(runtime, model_name)`
string) actually recognizes the model once it's on disk. After the Test 3
pull succeeds:

```bash
curl -s http://127.0.0.1:11434/api/tags
```

Confirm the returned `name` for that model is byte-identical to what was
requested (`hf.co/mradermacher/llama3.2-typhoon2-3b-instruct-GGUF:Q8_0`) —
specifically check Ollama didn't silently append `:latest`, drop the
`provider/` prefix, or otherwise reshape it, since any of those would make
the model permanently show as "not installed" in SurfSense despite being on
disk. Clean up with `ollama rm` (or `/api/delete`) afterward, same as Test 2.

## What to paste back here

1. The full stdout of the Test 1 analysis script.
2. The four JSON responses from Test 2 (pull's final `{"status":"success"}`
   line, the `/api/tags` entry for the model, the `/api/show` `template`
   field, and confirmation the delete succeeded).
3. The GPU/OS details of the machine it ran on (GPU model + VRAM, OS version)
   — grab this from the `"system"` key in `fit_output.json` rather than typing
   it manually, so it's exact.
4. Test 3: the full `/api/chat` response text, and the `ollama ps` output
   showing the `PROCESSOR` column.
5. Test 4: the exact `/api/tags` entry name for the Test 3 model, so it can be
   diff'd character-for-character against what was requested.

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

## Results — Windows GPU verification (2026-09-17)

**Machine:** NVIDIA GeForce RTX 3050 (6GB VRAM, CUDA), AMD Ryzen 5 9600X
(12 cores), 31.14GB RAM, Windows 11. From the `system` key in
`fit_output.json`:

```json
{
  "available_ram_gb": 15.43,
  "backend": "CUDA",
  "cpu_cores": 12,
  "cpu_name": "AMD Ryzen 5 9600X 6-Core Processor",
  "gpu_available_gb": null,
  "gpu_count": 1,
  "gpu_name": "NVIDIA GeForce RTX 3050",
  "gpu_vram_gb": 6.0,
  "has_gpu": true,
  "total_ram_gb": 31.14,
  "unified_memory": false
}
```

### Test 1 — raw llmfit scan characteristics

```
=== Basic counts ===
total scanned: 9361
has ollama_name: 138
has gguf_sources: 1625
gguf_sources only (net new if fallback ships): 1508

=== THE KEY QUESTION: runtime breakdown ===
runtime values across ALL scanned models: Counter({'llama.cpp': 8858, 'vLLM': 503})

runtime values for the gguf_sources-only group specifically:
Counter({'llama.cpp': 1508})

=== best_quant samples, grouped by runtime, for the gguf_sources-only group ===
  'llama.cpp' -> ['Q8_0', 'Q8_0', 'Q8_0', 'Q8_0', 'Q6_K', 'Q8_0', 'Q6_K', 'Q6_K', 'Q8_0', 'Q6_K']

=== Usable (Perfect/Good/Marginal) counts ===
usable today (ollama_name only): 115
usable with fallback added (either source): 1461
```

100% of the 1,508 `gguf_sources`-only rows have `runtime: "llama.cpp"`
(never MLX — MLX did not appear at all on this machine; the other runtime
seen was `vLLM`, on 503 models, none of which were in the `gguf_sources`-only
group). `best_quant` for this group is consistently a real GGUF quant tag
(`Q8_0`, `Q6_K`, etc.), not an MLX label.

Sample raw entry confirming the shape:

```json
{
  "name": "typhoon-ai/llama3.2-typhoon2-3b-instruct",
  "runtime": "llama.cpp",
  "best_quant": "Q8_0",
  "fit_level": "Perfect",
  "gguf_sources": [{"provider": "mradermacher", "repo": "mradermacher/llama3.2-typhoon2-3b-instruct-GGUF"}],
  "ollama_name": null,
  "verify_command": "llama-bench -m <path-to-Q8_0-gguf> -ngl 99 -p 512 -n 128"
}
```

(Aside: the throwaway analysis script's own `normalize()` helper had a bug —
it collapsed `"llama.cpp"` to `"llama_cpp"` instead of `"llamacpp"`, so its
"0 llamacpp rows" line was a script artifact, not a finding. The raw
`runtime` field is unambiguously `"llama.cpp"` for every one of these rows,
which is exactly what `_code()` in `llmfit.py` — which strips separators
rather than replacing them — normalizes to `"llamacpp"`.)

### Test 2 — Ollama `hf.co` pull round-trip

Ran against a local Ollama v0.33.3:

- **Pull**: final line `{"status":"success"}`
- **`/api/tags`**: entry `hf.co/bartowski/SmolLM2-135M-Instruct-GGUF:Q4_K_M`
  with `"quantization_level": "Q4_K_M"` — identifier byte-identical to what
  was requested
- **`/api/show`** `template` field: populated with a correctly auto-detected
  ChatML-style template (`{{- if .Messages }}...<|im_start|>...`)
- **`/api/delete`**: HTTP 200, model removed

Matches the Mac result exactly — no mangling of the `hf.co/...` identifier
on Windows either.

### Conclusion

Hypothesis confirmed on real GPU Windows hardware: `runtime` normalizes to
`llamacpp` and `best_quant` is GGUF-shaped for the entire `gguf_sources`-only
group. The runtime-gated `trusted_quant` design above is correct as written
— ship it as planned, no rethinking of the gating condition needed.

### Correction (found while reviewing these results — do not skip)

The "aside" above, and the code snippet in "The open question this spec
exists to answer", are both **wrong about what `_code()` actually produces**.
Checked the real implementation directly:

```python
def _code(value):
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

_code("llama.cpp")  # -> 'llama_cpp'   (the "." is REPLACED with "_", not removed)
_code("llamacpp")   # -> 'llamacpp'
```

`_code()` replaces non-alphanumeric runs with a single underscore — it does
not strip separators out. So the real, verified `runtime` string from llmfit
(`"llama.cpp"`, confirmed in the sample raw entry above) normalizes to
**`"llama_cpp"`** (with an underscore), not `"llamacpp"`. The planned gating
condition must therefore be:

```python
runtime = _code(row.get("runtime"))
trusted_quant = best_quant if runtime == "llama_cpp" else None  # underscore, not "llamacpp"
```

Written as `runtime == "llamacpp"` (no underscore), this condition would
never match real scan data on any platform — it would silently fall back to
the untagged/`fit: UNKNOWN` path 100% of the time, quietly losing the
fit-scoring benefit this whole test round was meant to validate. The
underlying test results and numbers above are unaffected by this — only the
exact comparison string in the implementation needs to use `"llama_cpp"`.

### Test 3 — real inference + GPU offload

Pulled `hf.co/mradermacher/llama3.2-typhoon2-3b-instruct-GGUF:Q8_0` (the
sample entry from Test 1) against the same local Ollama v0.33.3:

```
{"status":"pulling 804cbfae434f", ...}
{"status":"verifying sha256 digest"}
{"status":"writing manifest"}
{"status":"success"}
```

`/api/chat` response:

```json
{"model":"hf.co/mradermacher/llama3.2-typhoon2-3b-instruct-GGUF:Q8_0","created_at":"2026-09-17T10:58:00.7658425Z","message":{"role":"assistant","content":"Hello!"},"done":true,"done_reason":"stop","total_duration":6474871300,"load_duration":6345882400,"prompt_eval_count":17,"prompt_eval_cached_count":0,"prompt_eval_duration":72261000,"eval_count":3,"eval_duration":51625000}
```

`ollama ps`:

```
NAME                                                          ID              SIZE      PROCESSOR    CONTEXT    UNTIL
hf.co/mradermacher/llama3.2-typhoon2-3b-instruct-GGUF:Q8_0    a17ef7fd3227    4.0 GB    100% GPU     4096       4 minutes from now
```

Response is coherent, correctly-formatted prose ("Hello!") — the
auto-detected chat template works, not garbled. `PROCESSOR` shows **100%
GPU** — full GPU offload confirmed on the RTX 3050, no silent CPU fallback.

### Test 4 — end-to-end catalog loop

`/api/tags` entry for the Test 3 model, immediately after the pull:

```json
{
  "name": "hf.co/mradermacher/llama3.2-typhoon2-3b-instruct-GGUF:Q8_0",
  "model": "hf.co/mradermacher/llama3.2-typhoon2-3b-instruct-GGUF:Q8_0",
  "size": 3421899438,
  "digest": "a17ef7fd3227bc32fe019d04ec0ac830d4d36c0d844bd2720cc799818a1b3c52",
  "details": {
    "parent_model": "",
    "format": "gguf",
    "family": "llama",
    "families": ["llama"],
    "parameter_size": "3.21B",
    "quantization_level": "unknown",
    "context_length": 131072,
    "embedding_length": 3072
  }
}
```

`name` is **byte-identical** to what was requested
(`hf.co/mradermacher/llama3.2-typhoon2-3b-instruct-GGUF:Q8_0`) — no
`:latest` appended, no `provider/` prefix dropped, no reshaping. Confirms
`catalog.py`'s exact-string `installed_by_key` matching will correctly
recognize this model as installed once pulled. Model was deleted
(`/api/delete`, HTTP 200) after the check, same as Test 2.

One caveat worth noting for `catalog.py`: `details.quantization_level` came
back as the literal string `"unknown"` for this hf.co-sourced pull (unlike
the Test 2 SmolLM2 pull, which correctly reported `"Q4_K_M"`) even though the
quant tag `Q8_0` was explicitly requested and is present in the `name`/tag
string. Any downstream code that reads `quantization_level` from `/api/tags`
or `/api/show` to redisplay the installed quant (rather than parsing it out
of the `:Q8_0` suffix already present in `ollama_name`) would show
"unknown" for this model — something to check if the frontend ever surfaces
that field for installed models.

## Shipped

The fallback is merged. `_fallback_ollama_name(gguf_sources, runtime,
best_quant)` in `llmfit.py` returns `hf.co/<repo>:<best_quant>` when
`runtime == "llama_cpp"` and a quant is present, and `hf.co/<repo>:latest`
otherwise. Three details of the merged version are worth reading off the code
rather than off the spec above:

- **The gate uses `"llama_cpp"`, the underscore form.** The Correction section
  was right and the two earlier snippets in this document were wrong; the
  shipped condition matches the Correction, not the snippets.
- **The tag is never omitted.** The spec discussed an "untagged
  `hf.co/<repo>` pull" for the untrusted case. That is not what shipped:
  Ollama accepts a bare `hf.co/<repo>` but stores the result as
  `…:latest`, so every later exact-string match — install verification,
  "already installed" on a rescan — would fail against an identifier Ollama
  never used. The fallback therefore asks for `:latest` explicitly so the
  string handed out is the string that comes back.
- **The fit badge is downgraded, not cleared.** Where the spec said `fit:
  UNKNOWN`, the shipped `_parse_model()` relabels an untrusted fallback row to
  `FitLevel.MARGINAL` — a hedge rather than a promise, chosen over both hiding
  the model and carrying forward a number computed for a different runtime's
  memory profile.

Two related changes landed with it and are not described anywhere above:
`scan()` no longer spawns llmfit unless `refresh=True`, caching results to
`{data_dir}/llmfit-scan.json` (invalidated on a `cache_version` or
`llmfit_version` mismatch), and the catalog now serves its `curated` and
`installed` buckets with no scan at all. Only `explore` and the fit badges
need one, so the page opens on a fresh install with a "Scan hardware" call to
action instead of an empty list. The bucket formerly called `recommended` is
now `curated`.
