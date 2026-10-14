---
status: in-progress
code:
  - surfsense_local/backend/modules/llm/
  - surfsense_local/backend/modules/documents/
  - surfsense_local/backend/modules/events/
  - surfsense_local/backend/worker/
  - surfsense_local/backend/worker.py
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/backend/scripts/
  - surfsense_local/backend/tests/packaging/
  - surfsense_local/backend/bundling/
  - surfsense_local/backend/pyproject.toml
  - surfsense_local/electron/src/main/
  - surfsense_local/electron/src/preload/
  - surfsense_local/electron/scripts/audiocpp/
  - surfsense_local/electron/build/
  - surfsense_local/electron/electron-builder.yml
  - surfsense_local/electron/package.json
  - surfsense_local/frontend/src/features/
  - surfsense_local/frontend/src/lib/api.ts
  - .github/workflows/
---

# Local speech recognition

> Recordings become sources, and the chat composer gets a mic. Both run on the user's CPU, on a second instance of the [audio.cpp](https://github.com/0xShug0/audio.cpp) server the app already ships for podcast voices. The model is NVIDIA's Nemotron 3.5 ASR Streaming 0.6B: OpenMDW-1.1, all ten interface languages, 26 languages at 30% error or better on FLEURS, and language detection built in. Measured on audio.cpp's CPU path beside Qwen3-ASR-0.6B, the other candidate in the pin, it held half the memory (1.19 GB loaded against 2.37 GB) and ran three times as fast (11.5× real time against 3.9×) ([Measurements](#measurements)). The maintainer's rule was the model that takes the least of the user's machine.

This extends [local audio models](local-audio-models.md), which brought audio.cpp in for podcasts, and touches the local catalog and [selection](../architecture/local-models/selection.md), [ingest](../architecture/documents.md) and the [chat composer](../architecture/chat.md). It serves three aims: recordings as sources, voice input in the composer, and as many languages as possible on light hardware. The [glossary](../../.agents/skills/translate/glossary.md)'s *speech* means text read aloud, so this feature is **speech recognition** to the user, **transcription** in the backend and **dictation** in the composer.

## What changes

| | Today | With this |
|---|---|---|
| Speech recognition runtime | none | `audiocpp_server`, the binary already staged, run a second time as the `audiocpp-transcription` sidecar from `<data>/audio/transcription.json` |
| Families compiled | `kokoro_tts`, `supertonic`, `kitten_tts` | adds `nemotron_asr` |
| Model | none | Nemotron 3.5 ASR Streaming 0.6B `Q8_0`, 930.6 MB, downloaded on request |
| Selection | five slots | adds `speech_to_text`, local only, with the language intent in the row's `settings` |
| Sources | no audio | `.wav .mp3 .flac .ogg .oga` in v1; `.opus`, `.m4a`, `.aac` and audio-only `.webm` once an LGPL decode-only FFmpeg ships (step 9) |
| Composer | no mic | a mic beside Send; text lands phrase by phrase as the user speaks |
| Electron | no permission handler; no macOS mic entitlement | `media` granted for audio only, to the main window's own page; entitlement, usage string, a mic status bridge |
| Installer | no speech assets | the compiled family and a 1.3 MB voice-activity detection (VAD) model; no speech model ships |

## Why audio.cpp

**What is reused.** The podcast work's packaging ([Packaging](local-audio-models.md#packaging)): the per-CPU Windows build with no AVX-512 in the exe, the Linux `objdump` gate at glibc 2.34, upstream's macOS arm64 archive, staging, and the CI cache keyed on `scripts/audiocpp/*.mjs`. Also its sidecar spec and watcher, and the catalog slice with pinned, sha256-checked installs behind `host:huggingface.co` consent ([ADR 0027](../adr/0027-egress-consent-per-host.md)). `nemotron_asr` is already in the pinned v0.8.2 source. Adding it compiles 9 more source files and links no new library: sentencepiece, cJSON and libyaml are in every build. Built on Windows with the app's recipe flags and both measured families, the server compiled in about 4 minutes and its folder, every per-CPU library included, is 13 MB ([Measurements](#measurements)).

**What the pinned server already does** (v0.8.2, commit `4d88768`):

- `POST /v1/audio/transcriptions/details` takes a multipart `file`, `model`, `language`, `prompt` and `busy_timeout_ms`, and merges the model's `default_request_options` under the request's own ([`runtime.cpp`](https://github.com/0xShug0/audio.cpp/blob/4d88768fbcae4e6eb3352c6ab1422dabb7d90b58/app/server/runtime.cpp#L2656-L2746)). It refuses with 400 a filename with any extension but `.wav`; the check reads only the name, and a name with no extension passes.
- Nemotron detects the language when none is named. `/details` reports only a language the request named ([`session.cpp`](https://github.com/0xShug0/audio.cpp/blob/4d88768fbcae4e6eb3352c6ab1422dabb7d90b58/src/models/nemotron_asr/session.cpp#L297-L300)), but with the request option `keep_language_tags` the text carries the detected locale after each sentence, `… previsto. <es-ES>`, which the client reads and strips. Measured: the tag came back for en, es, pt and zh, and not for a Hindi clip that ended without punctuation.
- `GET /v1/models` reports `loaded` per model ([`runtime.cpp`](https://github.com/0xShug0/audio.cpp/blob/4d88768fbcae4e6eb3352c6ab1422dabb7d90b58/app/server/runtime.cpp#L3482)), and `POST /v1/tasks/unload_models` unloads the models listed in `model_ids` ([`runtime.cpp`](https://github.com/0xShug0/audio.cpp/blob/4d88768fbcae4e6eb3352c6ab1422dabb7d90b58/app/server/runtime.cpp#L3615)).
- `POST /v1/models/load` answers 403 "dynamic model management is disabled" unless the server runs with `--ui-management`, which the app never sets ([`runtime.cpp`](https://github.com/0xShug0/audio.cpp/blob/4d88768fbcae4e6eb3352c6ab1422dabb7d90b58/app/server/runtime.cpp#L1352-L1354)).
- It passes a language to Nemotron as one of its 40 locale codes, and fails the request on any other ([`session.cpp`](https://github.com/0xShug0/audio.cpp/blob/4d88768fbcae4e6eb3352c6ab1422dabb7d90b58/src/models/nemotron_asr/session.cpp#L216-L226)).

**What reuse costs.**

1. **Languages.** Nemotron lists 40 locales, and the handy-computer card measures 28 languages, 26 of them at 30% error or better. Bengali, Urdu, Tamil, Telugu, Swahili and Persian have no usable recogniser in the pin; Cantonese, Indonesian, Malay and Thai have one only in Qwen3-ASR. audio.cpp will not run Whisper: "I don't plan to implement Whisper models, since whisper.cpp already exists and is mature" ([#190](https://github.com/0xShug0/audio.cpp/issues/190)).
2. **Weight.** audio.cpp publishes Nemotron as `Q8_0` (930.6 MB) and `F16` only; [transcribe.cpp](https://github.com/handy-computer/transcribe.cpp), the runtime that [Handy](https://github.com/cjpais/Handy), an open-source offline dictation app, ships, has a 496 MB `Q4_K_M`. The levers are weight precision, which is upstream's, and the model chosen.
3. **Accuracy.** Nemotron trails Qwen3-ASR in Chinese (CER 18.87 against 7.57) and Japanese (13.52 against 8.61) on the cards; Qwen stays a candidate second model for them ([Order of work](#order-of-work)).
4. **Input.** The server reads WAV only, and the app has no audio decoder.
5. **Live text.** Nemotron is a cache-aware streaming model, but `/live` needs a client that streams audio up and reads text down on one request, which neither a browser `fetch` nor `httpx` is. v1 sends phrases offline.

**The fallback: transcribe.cpp**, MIT, which Handy runs in a crash-isolated child. It runs Whisper, Qwen3-ASR, Nemotron, Parakeet and SenseVoice, and its `transcribe-cpp-native` 0.4.0 wheels, uploaded 12 Oct 2026, are 18.3 MB on Windows, 22.8 MB on Linux and 2.5 MB on macOS. It is not v1: it has no server, so the app would host and supervise it; it is six months old with one main maintainer; and it would be a second ggml runtime to keep green. The API slice calls a `Transcriber` protocol in [`providers/protocols.py`](../../surfsense_local/backend/modules/llm/providers/protocols.py) (`transcribe`, `is_loaded`, `unload`), whose audio.cpp client is `providers/audiocpp/transcription.py`; the fallback would replace that client, the sidecar spec, `transcription_config.py` and the `local_runtime_type` CHECK. Shipping it would also need a Python-side Linux gate (today's refuses any staged file that needs libstdc++, libgomp or Vulkan, and a `manylinux_2_28` library probably needs libstdc++), proof that PyInstaller keeps ggml's per-instruction-set CPU libraries beside `libtranscribe`, a child mode in [`worker.py`](../../surfsense_local/backend/worker.py), which imports lazily, rather than the API's [`main.py`](../../surfsense_local/backend/main.py), a binding that takes a language and a thread count, and exact pins of both packages, which moved three minor versions between August and October 2026.

| Rejected runtime | Why |
|---|---|
| whisper.cpp | Whisper only; no unload, memory returns only at exit; macOS must be compiled |
| sherpa-onnx | multi-file ONNX models the catalog cannot install; a second onnxruntime beside the worker's 1.29; its Whisper reads only the first 30 s |
| faster-whisper | Whisper only; last release 31 Oct 2025; depends on PyAV, whose wheels link GPL code ([Licences](#licences)) |
| onnx-asr | too few families |
| Docling's ASR pipeline | openai-whisper on torch plus an `ffmpeg` on PATH, in the process that holds Docling |
| transformers.js | the renderer is the wrong process for ingest; single-threaded WASM under `file://` |
| assistant-ui's `WebSpeechDictationAdapter` | Chromium sends the audio to Google, against [ADR 0017](../adr/0017-egress-off-by-default.md) |

## Which model

Two recognisers in the pin cover all ten interface languages: Nemotron 3.5 and Qwen3-ASR-0.6B. Both were built and run on audio.cpp v0.8.2's CPU path with the app's flags, the same harness and the same audio ([Measurements](#measurements)):

| | Nemotron 3.5 ASR Streaming 0.6B | Qwen3-ASR-0.6B |
|---|---|---|
| Download, `Q8_0` | 930.6 MB | 1,151.3 MB |
| Resident once loaded | 1,189 MiB | 2,366 MiB |
| Peak, first request with the load | 1,776 MiB | 2,449 MiB |
| Peak over an 8.6-minute file in 28 s windows | 1,370 MiB | 2,642 MiB |
| Kept after `unload_models` | 10 MiB | 13 MiB |
| First request, load included, 24.7 s of speech | 4.3 s | 8.9 s |
| Speed on a warm 24.7 s window | 12.8× real time | 4.1× |
| Speed over the 8.6-minute file | 11.5× | 3.9× |
| English error on that file (LibriSpeech) | 6.5% | 4.4% |
| Languages at ≤30% FLEURS error (handy-computer cards) | 26 of 28 | 20 of 30 |
| Weights | OpenMDW-1.1 | Apache-2.0 |

**Nemotron is the model.** It takes half the memory and a third of the time, and serves more languages at usable accuracy; the maintainer's rule was the model that takes the least of the user's machine. Qwen is more accurate in English, Chinese and Japanese, and lists Cantonese, Indonesian, Malay and Thai, which Nemotron does not; it stays the candidate second model ([Order of work](#order-of-work)).

Error on FLEURS, %, from the handy-computer cards (`Q8_0`, one pipeline for every model, on a GPU): word error rate, and character error rate for ja, ko and zh; lower is better.

| | en | de | es | fr | hi | ja (CER) | ko (CER) | pt | ru | zh (CER) |
|---|---|---|---|---|---|---|---|---|---|---|
| Nemotron 3.5 | 7.90 | 10.33 | 6.30 | 10.78 | 8.61 | 13.52 | 8.89 | 8.52 | 12.61 | 18.87 |
| Qwen3-ASR-0.6B | 4.23 | 6.80 | 4.88 | 7.76 | 12.68 | 8.61 | 5.82 | 6.57 | 10.30 | 7.57 |
| Whisper small | 6.51 | 9.86 | 5.92 | 13.30 | 42.05 | 12.81 | 7.70 | 7.65 | 11.90 | 23.06 |

Others considered, with the cards' speed in transcribe.cpp on a Ryzen 7 PRO 4750U laptop CPU:

| Model | Download | 4750U CPU | Languages at ≤30% | Weights | Here |
|---|---|---|---|---|---|
| Parakeet TDT v3 | 916 MB (audio.cpp) | 13.66× | 24 of 25, European only; no ar, hi, ja, ko, zh | CC-BY-4.0 | a later second model for European files |
| Whisper large-v3-turbo | 536 MB (`Q4_K_M`) to 886 MB | 1.43× on short clips | 46 of 83 | MIT | not in audio.cpp (#190); only through the fallback |
| Whisper small | 270 MB | 5.86× | 23 of 81; hi 42.05, zh CER 23.06 | MIT | no |
| OWSM v4 base and small | 118 and 432 MB (audio.cpp) | unmeasured | unpublished | CC-BY-4.0 | needs v0.9.1 and an eval (step 8) |
| SenseVoice Small | 254 MB | 19.73× | 5 trained languages | FunASR custom | no |

- **Languages the app lists.** The 26 Nemotron's card measures at 30% or better: it 5.78, es, en, pt, hi, ko, de, fr, ru, ja, nl, vi, uk, tr, ar, pl, zh 18.87, nb, fi, bg, cs, sk, sv, hr, ro and da 28.51. Estonian (31.84) and Hungarian (32.12) are measured above 30% and not listed. Auto-detection still transcribes the other locales it knows, and the transcript says so ([Languages](#languages)).
- **One selected model serves both features**; the server holds one at a time. A second curated model is an alternative the user picks, never a second resident model.
- **Nothing light and broad in the pin.** No recogniser in it is both under about 500 MB and broad under a permissive licence. The light end of the aim starts with the pin moving to v0.9.1 and an eval of OWSM v4 base (118 MB at `Q8_0`, 151 language codes, 913 MiB peak on a desktop CPU, 80.1% language ID) and small (432 MB), step 8.
- **Not bundled.** 930.6 MB is more than the AppImage's 694 MB of headroom under GitHub's 2 GiB asset limit (v2.2.0's AppImage is 1.45 GB), GGUF barely compresses, and the models small enough to bundle are English-only, cover five languages, or are unevaluated and outside the pin. It downloads in one click from the mic, a waiting recording or Settings, with the existing consent. Transcribing is loopback, not egress.

## The runtime

### The transcription server

`sidecars/audiocpp-transcription.ts` returns a spec for the same binary as [`audiocpp.ts`](../../surfsense_local/electron/src/main/sidecars/audiocpp.ts), with its own config, port and flags, and no eSpeak:

| Flag | Value | Why |
|---|---|---|
| `--config` | `<data>/audio/transcription.json` | its own file, so a TTS install never restarts it |
| `--backend` | `cpu` | the GPU is the chat model's ([ADR 0012](../adr/0012-vulkan-only-gpu-backend.md)) |
| `--threads` | half the logical cores, at most 8 | `audioThreads()`, measured for voices |
| `--max-loaded-models` | 1 | one speech model at a time |
| `--idle-unload-ms` | 300000 | the backstop; Handy's default too |
| `--min-free-memory-mb` | 1024 | a backstop behind the app's own check |
| `--no-ui` | | as for voices |

- **Watcher.** `sidecars/watch-transcription-models.ts` follows the file as [`watch-audio-models.ts`](../../surfsense_local/electron/src/main/sidecars/watch-audio-models.ts) does: start when it exists, restart when it changes, stop when it is gone. Unlike the TTS server, it also restarts after a crash, at most once per 10 s, as [`boot.ts`](../../surfsense_local/electron/src/main/sidecars/boot.ts) restarts opencode. After 3 crashes in 5 minutes it stops trying; status then reports `transcription_unavailable`, and a recording that fails on it reads "The speech recognition engine stopped". Today a crashed audio server only notifies the renderer.
- **`transcription.json` is written only when its bytes change**, so an API start, a voice install or a delete never restarts it.
- **Only the API is told where it is.** [`python.ts`](../../surfsense_local/electron/src/main/sidecars/python.ts) adds `SURFSENSE_LOCAL_TRANSCRIPTION_BASE_URL` to the API's environment alone, as it does for opencode. Workers reach it through the API.
- **Settings › Resources** already files every `audiocpp_server` process under its audio.cpp row ([`engines.py`](../../surfsense_local/backend/modules/resource_usage/engines.py)), so the second one counts there with no change.

**Why a second process.** One server under today's flags fails four ways:

1. Eviction ignores the task, so a dictation evicts Kokoro between podcast turns.
2. Under `--max-loaded-models 1`, a request for another model that finds the resident one busy cannot evict it and fails with 503 `server_busy` ([`runtime.cpp`](https://github.com/0xShug0/audio.cpp/blob/4d88768fbcae4e6eb3352c6ab1422dabb7d90b58/app/server/runtime.cpp#L1890-L1893)), so a file transcription fails a podcast turn with `VoicingError`.
3. The podcast's closing `unload_all_models` unloads a warm dictation model, and waits without bound on a transcription in flight.
4. Every TTS install, delete and API start rewrites `server.json`, and Electron's restart kills transcriptions in flight.

A second process removes all four without touching the podcast. Measured, it holds 7 MiB at idle and 10 MiB after its model is unloaded ([Measurements](#measurements)).

### Residency

- The model loads on first need and unloads after 5 idle minutes.
- When a file's last window is done, the API unloads the model by id, unless a dictation session is open, as the podcast job does when it ends. The worker marks a window `last` when no other recording is pending or processing.
- When the API grants a hold of the text runtime (`/internal/models/text/yield`, which a podcast takes while voicing and a local image while drawing), the gate starts no new file window until the hold ends, waits for the request in flight, then unloads the speech model by id. Dictation stays available during a hold, behind the usual memory check, and its phrases then share the CPU with the voicing.
- **Speech never unloads or holds the chat model.** A reload costs 10 to 26 s ([runtime](../architecture/local-models/runtime.md)), and dictated text is about to be sent to that model. A shortfall is refused with a sentence instead.

### Memory

Before a request that would load the model, the API reads `GET /v1/models`. A model already `loaded` needs no check, since the operating system's figure already excludes it. Otherwise it applies the podcast's rule ([Memory](local-audio-models.md#memory)): the manifest's measured `peak_mb` plus 1 GiB against [`system_memory.available_bytes()`](../../surfsense_local/backend/modules/llm/hardware/system_memory.py). [`memory.py`](../../surfsense_local/backend/modules/llm/providers/audiocpp/memory.py)'s check takes a verb, so the sentence reads "Transcribing needs about {peak + 1 GiB} free; this computer has {available}." Once a second speech model is curated, it also names the first lighter one that would fit, as voicing does.

- **Dictation** is refused at once, `409 transcription_needs_memory`, before the user says anything.
- **A file window** waits while memory is short, checked every 5 s. The job sums those waits in `progress.json` across its yields, and past 10 minutes it fails with the sentence and no retry.
- **The server's own guard** estimates from the file size (the file × 1.5 + 128 MiB), not a measured peak, so it stays a backstop.

### The gate

`modules/llm/transcription/gate.py` sends every request to the transcription server, one at a time, as the server runs one model anyway. Speech recognition reaches its server only through the API from the start, as [ADR 0048](../adr/0048-the-api-is-the-only-path-to-a-text-model.md) requires of text models. The Known gap in [admission](../architecture/local-models/admission.md), Studio's image and audio calls reaching their servers directly, stays.

- **Dictation goes first.** A dictation phrase waits at most for the file window in flight, about 2.5 s for a 28 s window at the measured 11.5×.
- **A dictation session holds the gate open.** From mic press until its last phrase, or 20 s without a phrase or keepalive, no new file window starts, so the speaker's phrases never queue behind a file.
- **Deadlines grow with the audio**, as Handy's do: max(120 s, 20 × the audio's length) per request. A hung server fails one window, not the job.

## Catalog, selection and Settings

**The manifest block.** The `audio` block requires at least two voices, so recognisers get their own, reviewed like `audio`:

```jsonc
"transcription": {
  "origin": "nvidia/nemotron-3.5-asr-streaming-0.6b card; FLEURS from handy-computer/nemotron-3.5-asr-streaming-0.6b-gguf; memory measured on audio.cpp v0.8.2, Ryzen 7 5800X, 8 threads, 14 Oct 2026",
  "sample_rate": 16000,
  "peak_mb": 1776,                      // the first request, load included; the screen states it, admission reads it
  "window_s": 28,
  "detects_language": true,
  "languages": ["it", "es", "en", /* … the 26 under Which model */],
  "family_codes": { "en": "en-US", "pt": "pt-BR", "zh": "zh-CN" /* …: the locale the family takes for each listed language */ },
  "detected_only": { "et": "et-EE", "hu": "hu-HU" /* …: locales it may detect but is not listed for */ },
  "request_options": { "keep_language_tags": true }  // written as the entry's default_request_options
}
```

The schema refuses a `family_codes` key outside `languages`, a `detected_only` key inside it, and a `request_options` key the pinned family does not declare ([`loader.cpp`](https://github.com/0xShug0/audio.cpp/blob/4d88768fbcae4e6eb3352c6ab1422dabb7d90b58/src/models/nemotron_asr/loader.cpp#L76)). The multipart routes take no options, so `transcription_config.py` writes them as the entry's `default_request_options`, which the server merges under every request. The licence is authored from the source model, OpenMDW-1.1; the `audio-cpp/audio.cpp-gguf` repo itself is tagged `license:other`.

**The slice**, under [`engines/audiocpp/`](../../surfsense_local/backend/modules/llm/catalog/local/engines/audiocpp/):

- `manifest_fields.py` gains `TranscriptionDefaults`; [`registry.py`](../../surfsense_local/backend/modules/llm/catalog/local/engines/registry.py) has the engine run `(AUDIO_GEN, SPEECH_TO_TEXT)` with `entry_requires_one_of={"audio", "transcription"}`, as sdcpp does for images and video.
- [`classifier.py`](../../surfsense_local/backend/modules/llm/catalog/local/classifier.py) answers `SPEECH_TO_TEXT` for `nemotron_asr`; other recognisers stay typeless.
- `audio_folder/installed.py` and `server_config.py` keep only entries with `audio`. `audio_folder/transcription_config.py` writes `transcription.json`: `lazy_load`, then `{id, family, path, task: "asr", mode: "offline", session_options}` per installed recogniser, deleted when none is installed.
- Rows state the size, the memory while transcribing, that the model detects the language, and the languages it is listed for, a count that expands to the names. An install with `select: true` selects the row's own type.
- `scripts/local_manifest/` adds the entry; `VALIDATED` pins its file to v0.8.2.

**Selection.**

- `ModelType.SPEECH_TO_TEXT = "speech_to_text"` is a slot: speech models change freely, as voices do, while an embedder is bound to the index ([ADR 0037](../adr/0037-embedding-is-a-type-not-a-slot.md)).
- A hand-written revision after `0029` rebuilds `selected_models`, as `0016` and `0018` did: the type CHECK lists six slots, `local_runtime_type` lets `audiocpp` hold `audio_gen` or `speech_to_text`, it carries every column including 0019's `settings` (0018's rebuild predates it, so copying 0018 would drop saved voices), and its downgrade deletes `speech_to_text` rows. [`models.py`](../../surfsense_local/backend/modules/llm/models.py) mirrors the CHECK.
- **Local only.** [`selectable.py`](../../surfsense_local/backend/modules/llm/selectable.py) lets a model nothing recognises fill every slot; it stops at `speech_to_text`, since no remote speech client exists to call one.
- `selection.py` checks that the installed audio.cpp model carries `transcription`; `resolution.py` gains `resolve_speech_to_text()`.
- The language intent lives in the row's `settings`, under the slice's key, as voices live under theirs: `{"transcription": {"language": "auto"}}`. Like voices, it is dropped when the slot takes another model, since only a chat mode carries over ([`selection.py`](../../surfsense_local/backend/modules/llm/selection.py)); the step that curates a second model decides whether the intent should survive the switch.

**Settings › Speech recognition**, a section beside Audio, uses `ModelSlotSettings` with a `features/models/local/transcription/` slice (api, describe, download, catalog and delete hooks), and adds the language select ([Languages](#languages)). The Audio page already drops rows without `voicing`, so recognisers never appear there. Downloads install with `select: true`.

**The set-up popover**, shared by a waiting recording's row and the mic. "SurfSense turns your voice into text on this computer. It needs a one-time download." A card per curated model, with its size, its memory while transcribing, and "Works well in: …", its listed languages named with `Intl.DisplayNames`; **Download and set up** (the existing install job, `select: true`, the existing consent when egress is off), then a progress ring on the mic, then **Start talking**; **More choices** opens Settings. If the maintainer curates two models, the popover asks for the language first and offers the model that lists it.

## Audio files as sources

**Upload** ([`storage.py`](../../surfsense_local/backend/modules/documents/storage.py)):

- Suffixes with server-owned types: `.wav audio/wav`, `.mp3 audio/mpeg`, `.flac audio/flac`, `.ogg` and `.oga audio/ogg`.
- `_is_audio`, beside `_is_image`, checks RIFF/WAVE, ID3 or an MPEG frame sync, `fLaC`, and `OggS` with a Vorbis header. Ogg Opus is refused per file, "Opus support comes in a later update".
- The pinned [`test_upload_validation.py`](../../surfsense_local/backend/tests/unit/documents/test_upload_validation.py) and the frontend mirror in [`sources/api.ts`](../../surfsense_local/frontend/src/features/sources/api.ts) change with it; the composer's "Upload sources" then takes audio with no other change.
- [`layout.py`](../../surfsense_local/backend/modules/documents/source_figures/layout.py)'s `can_hold_figures` is false for `audio/*`; otherwise the figures pass would run Docling on a recording.
- The 500 MiB cap stays, and there is no duration cap. At 64 kbps that is about 18 hours: 2.1 GB decoded, and about 1.6 hours of transcription at 11.5×.

**The worker slice**, `worker/ingestion/audio/`, reached from `_markdown_from` in [`parsing.py`](../../surfsense_local/backend/worker/ingestion/parsing.py) before Docling. Everything it writes lives under the document's `transcript/` folder, because [`original_file.py`](../../surfsense_local/backend/modules/documents/original_file.py) needs the original to be the only file beside it. `transcript/work/` holds `audio16k.raw`, `plan.json`, `windows.jsonl` and `progress.json`; `transcript/segments.json` is written at the end.

1. **Ready?** The job asks the API's status route first. With no speech model it stops before decoding ([No speech model yet](#no-speech-model-yet)). With the server unavailable, as in the seconds after a model is chosen or a crash, it waits, checked every 5 s, for up to 2 minutes, yielding as below, then fails with retry.
2. **Room.** The duration from the file's headers × 115 MB per hour, plus 64 MB, is checked against free space on the data volume. Short of it, the document fails without retry: "Transcribing needs about {size} of free disk space." Running out of disk while decoding or writing a checkpoint is the same failure.
3. **Decode.** A child process decodes the file to 16 kHz mono 16-bit PCM (s16) in `audio16k.raw.part`, about 115 MB per hour, and renames it to `audio16k.raw` when it exits 0. In v1 the child is the worker itself, `worker --decode-audio <in> <out>`, dispatched in [`worker.py`](../../surfsense_local/backend/worker.py) ahead of the consumer's imports as `--run-document-script` is, streaming through pyminiaudio (`miniaudio` 1.71, MIT; wheels of 274 to 644 KB for every platform the app builds). It watches its stdin and exits when its parent does. A malformed file kills the child, not the ingest consumer. A decode error, or no samples at all ("This file has no audio."), fails the document without retry, as `UnreadableFileError` does.
4. **Speech spans.** Silero VAD (MIT), the 1.3 MB 16 kHz ONNX build on the onnxruntime 1.29 already in the worker and the API, one thread, threshold 0.5, minimum speech 250 ms, spans padded by 200 ms and merged across gaps under 300 ms. No span at all fails the document, "No speech was found in this recording", without retry.
5. **Cutting windows.** Spans pack into windows of at most 28 s, aiming at 24, cut at the longest pause. A single run past 28 s is cut at its quietest 100 ms between 20 and 28 s. Silence between windows is never sent, and every window keeps its offset in the recording, so timestamps survive; Handy's VAD joins the speech and drops the silence, which loses them. 28 s bounds a request's memory: Nemotron's offline mode runs one encoder graph over the whole request, and over 28 s windows it peaked at 1,370 MiB ([Measurements](#measurements)). The plan goes to `plan.json` once the VAD pass ends; a run that finds a `.part` file, or no `plan.json`, decodes again.
6. **The loop.** For each window not yet in `windows.jsonl`: check for cancel, send the window as an in-memory WAV to `POST /internal/transcription/windows` ([Transport](#transport)), append `{n, start_s, end_s, text, language}`, write `progress.json`, notify. A connection error or `503 transcription_unavailable` is retried after 1, 2, 4, 8 and 16 s.
7. **Finish.** The transcript becomes `content` through `finish_job`, as any file's text does; chunking, embedding, search, citations and the agent's `sources/` mirror take it unchanged. `transcript/segments.json` keeps `{model_id, language, duration_s, windows: [{line, start_s, end_s, language}]}` for seeking later; `transcript/work/` is deleted.

**Yielding.** The ingest queue has one thread, and a one-hour recording at 11.5× holds it for about 5 minutes, longer on a laptop. After each window, and after each `503 waiting` from the windows route, once 60 s have passed in this run and a document that is not a recording is pending, the job sets its row back to `pending`, unless cancelled, and queues itself again at `PRIORITY_BULK`. A PDF uploaded midway then starts within about a minute. Recordings never yield to each other. A yielded recording survives a restart, since the startup sweep fails only `processing` rows, and resumes from its checkpoint.

**Cancel and retry.**

- Cancel is checked between windows without holding the write lock, and lands within one window; the window in flight cannot be stopped. A yielded job's queued copy is revoked by the existing `revoke_pending`.
- No speech model, a memory refusal after its wait, no room on disk, no speech, no audio and an undecodable file fail without retry (`CancelExecution(retry=False)` in [`tasks.py`](../../surfsense_local/backend/modules/documents/tasks.py)).
- Anything else uses Huey's two retries. Every retry, Huey's or the user's, resumes from `windows.jsonl` when the model id and language intent match, so a long file is never transcribed three times. A failure that ends the job deletes `audio16k.raw` and keeps the window checkpoints.
- A recording the app quit in the middle of is failed by the startup sweep, as any source is ("interrupted when the app closed"). Retry resumes it from `windows.jsonl`.
- A speech model deleted between windows: the next window answers `409 needs_speech_model`, and the recording waits for a model ([No speech model yet](#no-speech-model-yet)), keeping `windows.jsonl` for when that model is chosen again. The window in flight holds `model_activity`, so a delete during it is refused.

**Progress.** `InternalEvent` gains an optional `progress {done_s, total_s}`, posted once per window and never stored, like chat's `prompt-progress` frame. `DocumentRead` gains `transcription {language, progress, awaiting}`; progress is read from `progress.json`, so a reload or a late listener sees it too, and is null once the recording is ready. [`document-row.tsx`](../../surfsense_local/frontend/src/features/sources/tree/document-row.tsx) shows "Transcribing · 23 of 58 min · about 7 min left" with a thin bar, the estimate from the speed of the windows done; a yielded file shows "Queued · 40% transcribed".

**The transcript.** One header line, then one paragraph per window, each starting with its time:

```markdown
Transcript of meeting.mp3 · 42:10 · Japanese (detected) · Nemotron 3.5. [hh:mm:ss] marks where each passage starts.

[00:00:00] …

[00:00:26] …
```

The chunker splits at blank lines ([`chunking.py`](../../surfsense_local/backend/worker/ingestion/chunking.py)), so while a window's paragraph stays under its 480 tokens ([Open questions](#open-questions)), every chunk's first line carries its start time and the agent can quote times. CJK text has no `. ` sentence breaks, so paragraphs keep chunk boundaries meaningful. The header language is the majority across windows; each window keeps its own. The job stores `transcription: {language, duration_s, model}` in the document's metadata.

**Text cleanup**, the same for files and dictation, and fail-open (on any error the text is kept as it is), as Handy's is: trim; collapse any run of one to four words (characters for zh, ja, yue and th) repeated four or more times to one; drop a window's text, and log it, when it runs past 40 characters per second of audio or its zlib compression ratio passes 2.4 over at least 50 characters. Runaway repetition is the known failure of autoregressive decoders such as Qwen's; Nemotron's transducer rarely repeats, and the guard costs nothing when it does not fire. No filler removal and no model rewriting in v1.

### No speech model yet

The upload is accepted. Finding no speech model, the job ends without retry and records `transcription.awaiting: true` in the document's metadata, which it removes when queued again. The row reads "Waiting for a speech model · Set up", not an error, and the link opens the set-up popover. Choosing a speech model queues every document whose `transcription.awaiting` is true at `PRIORITY_BULK`, so nothing is uploaded twice. A failed source is counted and not searched in a chat's scope, and Studio refuses it, as it does any unready source ([chat](../architecture/chat.md)), so this adds no new chat state. Rejecting at upload would throw the user's file away and hide the step that fixes it.

### Search caveat

Transcripts in every language are stored and reach the agent in full through `sources/`. Search finds them less well ([search](../architecture/search.md), Known gaps): the bundled bge-small is English-only, so a question in one language finds a transcript in another for 1 or 2 of 8 queries, and FTS5 keeps a Japanese or Chinese clause as one token. When a transcript's language is not English and the active index uses bge-small, the row and the preview say so in one line: "This recording is in Japanese. Search finds it best with questions in Japanese; add it to a chat to have all of it read." No embedder is switched. The fixes are their own proposals: a [multilingual embedder](retrieval.md), [changing the embedder](embedding-model-change.md) (deferred) and [CJK keyword search](cjk-keyword-search.md).

## Dictation

### Capture and phrases

`features/dictation/capture/`:

- `getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true}})` on the default device feeds an `AudioContext({sampleRate: 16000})` and an AudioWorklet loaded with `new URL(..., import.meta.url)`, the way pdf.js's module worker already loads over `file://`. If a platform refuses the 16 kHz context, capture runs at the device rate and each phrase is resampled with an `OfflineAudioContext`.
- The worklet posts 20 ms frames and their level. The noise floor is a running 10th percentile over 3 s; speech is three times above it and above a fixed minimum, set in the capture test (step 7).
- **A phrase ends at a pause:** at least 1.0 s of voice followed by 700 ms below the threshold, or a forced cut at 20 s at its quietest 200 ms. Each phrase keeps 450 ms before and after it (Handy's pre-roll and hangover); the tail also guards the last word.
- Phrases are s16 mono WAV, held in memory only, until transcribed or for Retry. Nothing is written to disk. Every track stops and the context closes on stop, cancel, thread switch, unmount and quit, which clears the OS mic indicator.

Phrase by phrase, not one batch on stop: at 11.5×, a 60 s dictation sent as one batch waits about 5 s after stop; sent by phrase, it waits only for the last phrase, well under a second for 4 s of speech. It needs no new transport and no streaming model.

### Transport

The renderer never talks to a sidecar ([`preload`](../../surfsense_local/electron/src/preload/index.ts)), and cannot stream a request body over HTTP/1.1, so each phrase is one POST to the API, under `/llm`, which the Vite dev proxy already covers:

| Route | Body → answer |
|---|---|
| `GET /llm/transcription/status` | → `{ready, reason: needs_speech_model or transcription_unavailable or null, model, language_intent, languages}` |
| `POST /llm/transcription/dictations` | → `201 {id, warm: loaded or loading}`; `409 needs_speech_model`; `409 transcription_needs_memory` with `needed_bytes`, `available_bytes` and an English `message`; `503 transcription_unavailable` |
| `POST /llm/transcription/dictations/{id}/phrases` | multipart `audio`, a WAV of 16 kHz mono s16, at most 30 s → `{text, language, no_speech}`; `404 dictation_ended` for a session the API does not know |
| `POST /llm/transcription/dictations/{id}/keepalive` | every 10 s while recording → `204` |
| `DELETE /llm/transcription/dictations/{id}` | → `204` |
| `POST /internal/transcription/windows` | a file window from the ingest worker, multipart → `200 {text, language, model_id}`; after at most 30 s of waiting, `503 waiting {reason: dictation, hold or memory}`, with both sizes for memory; `409 needs_speech_model`; `503 transcription_unavailable` |

The worker meets `503 waiting` by checking for cancel and the yield rule, then asking again: a hold's wait has no bound, and memory waits count toward the job's 10 minutes ([Memory](#memory)). `409 needs_speech_model` makes the recording wait for a model, and `503 transcription_unavailable` is retried.

- Opening a session ends any other open one, whose pending phrases still answer. It takes the gate's dictation hold and, when `/v1/models` says the model is not loaded and memory admits it, sends a 0.5 s silent WAV whose result is discarded, so the model loads while the user starts speaking.
- A phrase is checked with stdlib `wave`, then Silero: under 250 ms of speech answers `no_speech` without calling the model, so a cough or a keystroke never becomes text.
- The API forwards the phrase from memory as multipart to `/v1/audio/transcriptions/details` with the model id and the resolved language, applies the cleanup, and holds `model_activity` for the request, so a delete in the middle answers `ModelBusyError`. A phrase after the model is deleted ends the session: "The speech model was removed."
- A connection error or 503, as during a server restart, is retried once after 2 s. Sessions end after 6 minutes. A `404 dictation_ended`, as after an API restart, stops the composer: "Voice input stopped; what was transcribed is kept."

### How text lands

`features/dictation/dictation-adapter.ts` implements assistant-ui 0.15.18's `DictationAdapter`, passed in `adapters` in `use-chat-runtime.ts` whether or not the model reads images, with `disableInputDuringDictation: false`:

- `listen()` returns a session in `starting`; it becomes `running` on the first real frame.
- After each phrase it emits `onSpeech({transcript, isFinal: false})`, where `transcript` is every phrase so far joined by `join-phrases.ts`: no space between zh, ja, yue and th phrases, a space otherwise. assistant-ui puts a space between finals, which is wrong for CJK, so there is one final only.
- `stop()` flushes the tail, waits for pending phrases, emits `isFinal: true`, and only then sets `ended`: the runtime's cleanup drops anything emitted after.
- The textarea is `readOnly` while a session runs. It keeps focus and keydown, and the runtime's rebase cannot duplicate the cumulative text.
- Text is clamped to what is left under `QUESTION_MAX_CHARS`, 4,096, at the last word boundary (last character for zh, ja, yue and th), since the backend answers 422 past it. At the limit recording stops: "Voice input stopped at the 4,096-character message limit." A warning shows at 4:30 and recording stops at 5:00. A blank result inserts nothing.

### States and keys

Everything shows inside the composer, never above it, where the model notice and the scroll button sit. In the center placement the strip takes the place of the source count and model control while active; in the bottom placement it takes the disclaimer's.

| State | What shows |
|---|---|
| Idle | the mic, `Button size="icon-lg" variant="ghost"`, tooltip "Voice input stays on this computer" |
| Not set up | the mic, enabled; it opens the set-up popover |
| Arming | muted pulsing bars until the first real frame; no timer yet (Handy) |
| Listening | a red dot, 9 level bars, a timer from the first frame, a cancel ✕; phrases appear as they land |
| Loading | "Loading the speech model…", only after 2 s of loading, as Handy delays its live notice |
| Finishing | a spinner and "Transcribing…" |
| Error | one line and one action |

| Input while recording | Effect |
|---|---|
| Enter, or Send | stop, wait for the last phrase, insert; nothing is sent |
| Escape | cancel: untranscribed audio is dropped and the box returns to its text before the mic was pressed |
| Click the mic | stop and keep the text |
| Hold the mic 300 ms or more | push to talk; release stops (Handy's hold-or-toggle) |
| Space or Enter on the focused mic | toggle |

- Enter is caught in the composer's `onKeyDown`, which runs before assistant-ui's and can `preventDefault`, because `send()` cancels a running session and would drop audio not yet transcribed. Stop-and-send is the maintainer's call ([Open questions](#open-questions)).
- A thread switch cancels, never stops, so no late text lands in the next thread. Blur and minimise keep recording.
- The mic is disabled whenever the textarea is, and when the composer is already at its limit.
- No new shortcut in v1: Handy's Ctrl+Space is the input-method switch on CJK systems, and Cmd/Ctrl+Shift+D already toggles the theme.
- `aria-pressed` and localised labels on the mic, a `role="status"` line for Listening, Transcribing and errors, `role="alert"` for errors, and a still level dot under `prefers-reduced-motion`. The mic and the strip live in `features/dictation/` and the composer renders them, so their ids are `dictation_<surface>_<purpose>` and the server's codes `dictation_error_<code>` ([localization](../architecture/localization.md)).

**Errors.** `NotAllowedError` or a denied OS status: "Microphone access is off for SurfSense", with **Open settings**. `NotFoundError`: "No microphone found." `NotReadableError`: "The microphone is in use by another app." A track that ends: "The microphone was disconnected. What you said before that is kept." `transcription_needs_memory`: `dictation_error_transcription_needs_memory` formats the two sizes, with the server's English `message` as the fallback. A failed phrase: "Couldn't turn part of your speech into text", with **Retry** from the kept audio, as Handy does.

### Permissions

Electron approves every permission request by default, so any frame could open the mic silently today.

- `src/main/permissions/handlers.ts`, installed on `session-created` as [`spellcheck.ts`](../../surfsense_local/electron/src/main/spellcheck.ts) is, sets the session's request and check handlers. `permissions/media.ts` grants `media` only to the main window's main frame, on the app's own page (`file:` packaged, `http://localhost:5173` in dev), for audio alone; video and `display-capture` are denied. Every other permission keeps returning true, so clipboard writes and Copy do not regress; a strict allowlist needs an audit of its own. [`confine-snapshot-session.ts`](../../surfsense_local/electron/src/main/docx-snapshot/confine-snapshot-session.ts) denies the `docx-snapshot` partition everything.
- `src/main/microphone/ipc.ts`, behind the trusted-sender check, bridged as `window.surfsense.microphone = {status, request, openSettings}` and typed in `frontend/src/lib/api.ts`: `getMediaAccessStatus` on Windows and macOS, `askForMediaAccess` on macOS before `getUserMedia`, and `ms-settings:privacy-microphone` or the macOS Privacy pane, which `allowedExternalUrl` cannot open since it passes only https.
- macOS: `com.apple.security.device.audio-input` in [`entitlements.mac.plist`](../../surfsense_local/electron/build/entitlements.mac.plist), which `entitlementsInherit` shares with the helpers, and `mac.extendInfo.NSMicrophoneUsageDescription`, "SurfSense turns your speech into text on this computer.", in `electron-builder.yml`. Apple requires the entitlement under the hardened runtime ([Apple](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.device.audio-input)), and Electron's `askForMediaAccess` requires the usage string ([Electron](https://www.electronjs.org/docs/latest/api/system-preferences)). Handy declares the same pair.

## Languages

- The intent is `auto` or a language code, stored in the slot's settings and never rewritten from a detection, as Handy never writes back its `effective_language`. An intent the model does not list falls back to auto.
- Settings offers "Detect automatically", shown only when the model detects language, and the model's listed languages, labelled with `Intl.DisplayNames` in the interface language.
- `modules/llm/transcription/languages.py` maps the intent to the family's locale from the manifest (Nemotron takes "ja-JP"), and reads the detected locale from the last `<xx-XX>` tag in the text, which it strips, back to a code through `family_codes` or `detected_only`. A text with no tag keeps the intent, or no language when the intent is auto.
- **A detected language the model is not listed for** keeps its code and name from `detected_only`. The header reads "Swedish (detected) · lower accuracy with this model", the row says so in one line, and if another curated model lists the language, the line offers it. A name in neither map is kept in `segments.json`, and the header reads "language not identified". Both count as not English for the search caveat.
- The interface language is never taken as the spoken one.
- Files: per window, unless pinned ([Open questions](#open-questions) holds the rule that would lock a file to its first windows). Dictation: per phrase, unless pinned, so a speaker can switch languages between phrases.

## Licences

| What | Licence | When |
|---|---|---|
| Nemotron 3.5 ASR Streaming 0.6B weights | OpenMDW-1.1: "without restriction", the licence and notices kept on redistribution; added to the [allowlist](../../surfsense_local/backend/scripts/local_manifest/licence.py). The app downloads the weights from Hugging Face and does not redistribute them. | v1 |
| pyminiaudio; miniaudio and its dr_wav, dr_flac, dr_mp3 and stb_vorbis decoders | MIT; public domain or MIT-0 | v1, in the notices |
| Silero VAD ONNX | MIT | v1, in the notices |
| Qwen3-ASR-0.6B | Apache-2.0, already on the allowlist | later, as a second model |
| FFmpeg, decode only | LGPL, a separate executable with its text and an exact source pointer ([runtime licence policy](file-agent/04-runtime-and-packs.md)) | next |
| Parakeet v3, Canary, OWSM v4 | CC-BY-4.0, with an attribution notice | later, after review |
| SenseVoice, Moonshine outside English, MMS, CrisperWhisper | custom, community or non-commercial | excluded |

The runtime licence policy keeps GPL and LGPL code out of the app's own binaries, the PyInstaller bootloader's exception aside: LGPL may ship as a replaceable shared library, GPL only as a separate executable. Official PyAV wheels bundle an FFmpeg that links x264 and x265, both GPL-2.0-or-later; pyav-ffmpeg patches FFmpeg's configure so that build still calls itself LGPLv3. The LGPL fork, now BasswoodAV, is archived. So PyAV is not used, and step 9's gate looks for linked external libraries, not only `--enable-gpl`. AAC decoding already ships with the app: Electron builds its FFmpeg with proprietary codecs by default ([`all.gn`](https://github.com/electron/electron/blob/main/build/args/all.gn)), and the app does not replace it. Whether the decode-only FFmpeg may carry AAC is settled before `.m4a` ships.

## Packaging and CI

- [`pins.mjs`](../../surfsense_local/electron/scripts/audiocpp/pins.mjs): `FAMILIES` gains `nemotron_asr`; the recipe compiles only `FAMILIES` and stages their specs. `stage.mjs` returns early when a server is staged, so developers delete `electron/audiocpp/` once.
- [`build-audiocpp.yml`](../../.github/workflows/build-audiocpp.yml) re-runs the Linux `objdump` gate and the Windows per-CPU check with the new family, checks that upstream's macOS v0.8.2 archive contains it, and records the staged size and compile time.
- `tests/packaging/test_audiocpp_transcription.py`, added to the workflow's path filter: Kokoro voices known sentences in en, es, fr, hi, pt-BR and zh, the transcription server writes them down through the app's client, and the test asserts error and detected-language thresholds and records peak memory. No fixture with a licence of its own is needed. The model file is cached by its manifest sha256, unlike the voicing step's downloads, which run every time (step 4).
- `scripts/fetch_silero_vad.py` stages `silero_vad_16k_op15.onnx` (1,289,603 B) from a pinned commit of snakers4/silero-vad, sha256-checked, into the models pack beside the bundled voice, run beside `fetch_bundled_voice.py` by [`release-local.yml`](../../.github/workflows/release-local.yml) and the electron `package.json` scripts; the API and worker read it in place (step 4).
- `pyproject.toml` adds `miniaudio`; `bundling/worker.spec` collects it. `cffi`, which it needs, is already locked at 2.1.1 (step 5).
- There is still no installer size gate in CI.

## Order of work

Each step ships alone and leaves the app working. Steps 1 to 7 are v1.

1. **The measurement, no app change. Done** on 14 Oct 2026 ([Measurements](#measurements)): Nemotron 3.5 and Qwen3-ASR-0.6B on audio.cpp v0.8.2 built with the app's recipe flags. Nemotron took half the memory and a third of the time, so it is the model.
2. **The runtime, staged and invisible.** `FAMILIES`, the Linux `objdump` and Windows per-CPU gates, the macOS archive check, the sidecar spec, its watcher with crash restart, and the API's URL. Nothing writes `transcription.json` yet, so nothing starts. Adds ADR 0055, or the next number free then (0040 to 0046 are proposed by the file-agent work): "Speech recognition runs on a second audio.cpp server that only the API calls". Updates [`packaging.md`](../architecture/packaging.md).
3. **Catalog, selection and Settings.** The type, the revision, the slot, the manifest block and entry, the classifier, `transcription.json`, the rows and the Settings section. Users can install and choose a speech model; nothing reads it yet, which [selection](../architecture/local-models/selection.md) allows. Updates [`data-model.md`](../architecture/data-model.md), [`selection.md`](../architecture/local-models/selection.md) and [`catalog.md`](../architecture/local-models/catalog.md), and adds glossary rows for "speech recognition", "dictation" and "transcript", apart from the "speech" row.
4. **The API slice,** `modules/llm/transcription/` (router, internal router, gate, sessions, admission, selected model, languages, audio checks, cleanup, Silero) and the provider client behind the `Transcriber` protocol, with the hold rule and `fetch_silero_vad.py`. Tested against a fake server, and against the staged server by `test_audiocpp_transcription.py`; no screen changes. Extends the ADR with the gate, and updates [`admission.md`](../architecture/local-models/admission.md) and [`studio.md`](../architecture/studio.md).
5. **Audio files as sources,** with `miniaudio`, yielding, progress, cancel, awaiting rows and the set-up popover they open, and the search caveat in the same release, because without yielding one recording blocks every upload and note. Updates [`documents.md`](../architecture/documents.md) and `data-model.md`.
6. **The microphone in Electron,** and a notarized macOS build that shows the prompt. Updates `packaging.md`.
7. **Dictation,** phrase by phrase. Updates [`chat.md`](../architecture/chat.md). Folds v1 into `architecture/`, moves steps 8 to 11 into a new `proposals/speech-recognition-next.md`, and deletes this file.
8. **Next: light and broad languages.** The pin moved to v0.9.1 or later on its own, with the TTS peaks and the voicing gate re-run, then OWSM v4 base and small after a FLEURS eval of ar, hi, bn, ur, ta, te, sw, uk, he and fa, listing only the languages that pass.
9. **Next: more formats.** `scripts/ffmpeg-decode/` builds a pinned FFmpeg in CI on `ubuntu-22.04`, Windows and macOS arm64 with `--disable-everything --disable-network --disable-autodetect`, only the needed demuxers, decoders and parsers, `aresample` and a `pcm_s16le` WAV muxer, gated on `-buildconf` showing no `--enable-gpl`, `--enable-nonfree` or `--enable-lib` option, on fixtures in every allowed format and on the `objdump` floor. The worker runs it as the decode child, with a timeout. `.opus` joins; `.m4a` and `.aac` join once the AAC question is settled; `.webm` joins only for a file whose only stream is audio, until the maintainer answers the video question. Evaluated beside it: decoding in the renderer through Electron's own FFmpeg for files added from the window, streamed in chunks to 16 kHz mono WAV.
10. **Next: listen and seek.** `GET /documents/{id}/original` commits before its `FileResponse`, since every transaction is `BEGIN IMMEDIATE` and a player would hold the write lock, as Studio's file route does. An audio viewer joins the [source preview](source-preview.md)'s registry, with the transcript beside it, and a citation of a recording opens it at the time from `segments.json`.
11. **Later, each its own step and measurement:**
    - a Nemotron `Q4_K` package, asked of upstream (transcribe.cpp's `Q4_K_M` is 496 MB);
    - Qwen3-ASR-0.6B as a second curated model, for Chinese, Japanese, Cantonese, Indonesian, Malay and Thai, with the set-up popover asking for the language first;
    - if OWSM fails the Indic and African languages, transcribe.cpp with Whisper large-v3-turbo and Whisper fine-tunes such as `vasista22/whisper-tamil-small` (Apache-2.0), routed per language, put to the maintainer with the long-file Whisper measurement;
    - live partials from Nemotron's streaming mode over `/live`, with a WebSocket from the renderer and a full-duplex client in the API; with a second curated model, an ADR on whether per-language error rates may reach the screen ([ADR 0026](../adr/0026-curated-order-is-list-position.md) sends no score to it);
    - custom words through the request's `prompt`, a per-upload language, Chinese script conversion, an "unload right away" setting for low memory, and a remote speech client.

## Decided here

The maintainer set the rule for the model, the one that takes the least of the user's machine, and left the rest to this proposal's recommendations, which a review can overturn.

- audio.cpp v0.8.2 is the speech recognition runtime, as a second process from the same binary, with its own config, port and crash restart, called only by the API. transcribe.cpp is the fallback, behind the `Transcriber` protocol.
- Nemotron 3.5 ASR Streaming 0.6B `Q8_0` is the one curated model in v1, and OpenMDW-1.1 joins the licence allowlist.
- `speech_to_text` is a local-only slot; the language intent lives in its settings. One selected model serves files and dictation, downloaded, never bundled.
- Speech never unloads or holds the chat model. Memory is checked against the measured peak plus 1 GiB unless the model is already loaded; dictation is refused at once, a file waits up to 10 minutes in all. Dictation stays available during a podcast's or an image's hold.
- One API gate sends every request to the server: dictation first, file windows paused during a dictation session and during a text-runtime hold, which also unloads the speech model.
- Files are decoded in a child process, pyminiaudio in v1 (WAV, MP3, FLAC, Ogg Vorbis) and an LGPL decode-only FFmpeg executable next (Opus, M4A, AAC, audio-only WebM); PyAV is not used.
- Silero VAD on onnxruntime gates every window and phrase; windows are at most 28 s; silence is never sent.
- Transcription runs inside `ingest_document`, yields to other ingest every 60 s, resumes from a checkpoint, and reports transient progress.
- Transcripts are `[hh:mm:ss]` paragraphs in `content`, with `segments.json` for seeking and no new chunk columns. A recording with no speech fails.
- Audio uploaded before any speech model waits and is queued again when one is chosen.
- Dictation is phrase by phrase over multipart POSTs, in memory only, with one final result; live partials come later. Enter while recording stops and inserts; it never sends.

## Open questions

Each is a measurement with its rule already set, and the step that takes it:

- **Nemotron on a laptop (step 2).** Speed and peak memory on the i5-1235U and on an 8 GB Windows laptop with a 4B `Q4_K_M` chat model loaded, and error on about 50 FLEURS test utterances in each of the 26 listed languages. A language over 30% on audio.cpp's package is dropped from `languages`. Below 3× real time on the laptop, file windows shrink to 15 s so dictation waits less behind them.
- **Language tags (step 4).** How often a phrase or window comes back with no `<xx-XX>` tag. Above 1 in 10, the API reads the language from the text's script before giving up.
- **Whisper large-v3-turbo on long files** in transcribe.cpp, which only short clips have measured (1.43×): the number that decides whether the fallback can carry the long tail (step 11).
- **Language flips in files (step 5).** How often windows of a one-language recording are detected as another. Above 1 window in 20, a file locks to the majority of its first three speech windows.
- **Hallucination (step 5).** An hour of meeting audio and 10 minutes of music and noise, with and without the Silero gate and the compression-ratio drop. A guard that drops real speech from the FLEURS subset is removed.
- **Transcript chunks (step 5).** Tokens per 28 s window in each listed language under the chunker's tokenizer. A language whose windows pass 480 tokens gets shorter windows, so every chunk keeps its time.
- **Decoding (step 5).** pyminiaudio's time for an hour of MP3, and error with its linear resampler against scipy's `resample_poly`, already bundled. A loss above 2% relative moves resampling to scipy.
- **Yielding (step 5, before release).** A PDF uploaded midway through an hour's transcription starts within 90 s. Chat's tokens per second while a file transcribes, on a CPU-only laptop: a slowdown above 30% pauses file windows while a local reply generates, too.
- **Capture in packaged builds (steps 6 and 7).** The 16 kHz context and the worklet over `file://` on Windows, macOS and Linux, and the macOS prompt with the new entitlement. A platform that refuses 16 kHz resamples per phrase.
- **Language ID on short phrases (step 7).** Auto-detection on 3 to 8 s clips in the listed languages. Below 90%, the set-up popover asks for the language before the first recording.
- **Phrases against whole utterances (step 7).** Error on 60 s dictations cut at pauses against sent whole. Worse by more than 10% relative: phrases need 2 s of voice and a 900 ms pause.

Later, for the maintainer:

- If OWSM fails the eval, a second runtime for the long tail?
- CC-BY-4.0 onto the allowlist, for Parakeet v3 and OWSM?
- A `Q4_K` conversion hosted under SurfSense's own Hugging Face organisation, if upstream does not publish one?
- `.mp4`, `.mkv` and `.webm` with video, for their audio, once FFmpeg lands?

## Measurements

14 Oct 2026, Windows 11, AMD Ryzen 7 5800X (8 cores, 16 threads), 16 GB. audio.cpp v0.8.2 (`4d88768`) built with the app's recipe flags (CPU only, per-CPU ggml libraries, OpenMP off) and `AUDIOCPP_MODELS=qwen3_asr,nemotron_asr`; configured and compiled in about 4 minutes with 8 jobs; the output folder is 13 MB. One server per model: `--backend cpu --threads 8 --max-loaded-models 1`, one entry `task: asr, mode: offline`, requests multipart to `/v1/audio/transcriptions/details`. Files are the `Q8_0` packages from `audio-cpp/audio.cpp-gguf` at revision `f861648`, sha256-checked. Resident memory is the server's working set, sampled every 25 ms.

Audio, all 16 kHz mono: a 24.7 s window and an 8.6-minute file (73 utterances joined with 0.5 s gaps, sent as 22 windows of at most 28 s cut at the gaps) from `hf-internal-testing/librispeech_asr_dummy`; and one sentence in each of en, es, fr, hi, it, pt and zh, 9 to 14 s, voiced by the app's own Kokoro through the podcast server.

| | Nemotron 3.5 | Qwen3-ASR-0.6B |
|---|---|---|
| Server idle | 7 MiB | 7 MiB |
| First request, 24.7 s, load included | 4.28 s, peak 1,776 MiB | 8.91 s, peak 2,449 MiB |
| Resident after it | 1,189 MiB | 2,366 MiB |
| Warm 24.7 s window, best of 3 | 1.92 s (12.8×) | 6.00 s (4.1×) |
| 8.6-minute file in 22 windows | 45.1 s (11.5×), peak 1,370 MiB | 133.7 s (3.9×), peak 2,642 MiB |
| Word error on that file | 6.5% | 4.4% |
| After `unload_models` | 10 MiB | 13 MiB |

Kokoro sentences, error against the text voiced (word error; character error for zh), with no language named and with one named; the two matched for both models:

| | en | es | fr | hi | it | pt | zh |
|---|---|---|---|---|---|---|---|
| Nemotron 3.5 | 0 | 12.0 | 11.1 | 0 | 0 | 0 | 7.1 |
| Qwen3-ASR-0.6B | 0 | 0 | 0 | 5.0 | 7.7 | 0 | 1.8 |

Nemotron's Spanish error is a number written as digits ("un 12" for "un doce por ciento"); its French one is "plutôt que" heard for "plus tôt que". Qwen named every language it detected; Nemotron named none until `keep_language_tags` was set, and then tagged en, es, pt and zh and not the Hindi sentence, which ends without punctuation. Kokoro speech is clean and synthetic, so these say both models work in these languages, not how well on real recordings; the laptop measurement under [Open questions](#open-questions) takes the cards' FLEURS figures to audio.cpp's packages.
