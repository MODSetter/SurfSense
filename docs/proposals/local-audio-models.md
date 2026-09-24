---
status: in-progress
code:
  - surfsense_local/backend/modules/llm/catalog/local/
  - surfsense_local/backend/modules/llm/providers/
  - surfsense_local/backend/modules/artifacts/podcast/
  - surfsense_local/backend/scripts/local_manifest/
  - surfsense_local/backend/alembic/versions/
  - surfsense_local/electron/src/main/sidecars/
  - surfsense_local/electron/scripts/
  - .github/workflows/
  - surfsense_local/frontend/src/features/models/
---

# Local audio models

> Podcasts are voiced by an audio model the user downloads and chooses, like a chat or an image model, run by [audio.cpp](https://github.com/0xShug0/audio.cpp)'s server. It replaces the Kokoro that runs inside the worker on Python and ONNX today.

This extends the local catalog ([`catalog.md`](../architecture/local-models/catalog.md)) and the [model catalog proposal](model-catalog.md) with a third local runtime, and changes how Studio voices a podcast ([`studio.md`](../architecture/studio.md)). It follows the layout the image work introduced: one slice per engine under [`catalog/local/engines/`](../../surfsense_local/backend/modules/llm/catalog/local/engines/), behind one seam, [`LocalEngine`](../../surfsense_local/backend/modules/llm/catalog/local/engines/engine.py).

## What changes

| | Today | With this |
|---|---|---|
| Voice runtime | `kokoro-onnx` in the worker, on onnxruntime, eSpeak through `phonemizer` | `audiocpp_server`, a sidecar Electron starts, like `llama-server` and `sd-server` |
| Voice model | Kokoro-82M ONNX, 340 MB, bundled in the installer | curated models downloaded from the catalog, Kokoro first |
| Choosing one | not possible: `resolve_text_to_speech()` always returns Kokoro | the `audio_gen` selection, provider `audiocpp` |
| Podcast gate | `requires_voice`, "Needs a voice model" | `audio_gen` among the format's required model types, "Needs an audio model" |
| Voices | a list hard-coded in [`providers/kokoro/provider.py`](../../surfsense_local/backend/modules/llm/providers/kokoro/provider.py) | each model's roster, committed in the manifest |

The installer loses the 340 MB of Kokoro weights and three Python packages, and gains the sidecar. A podcast needs one download first, so the root README's two lines that say the podcast voice ships inside the installer change with the step that removes it.

## Why audio.cpp

- **One runtime for many voice models.** It runs 40-odd TTS families from one ggml binary, each as a standalone GGUF, the same shape the app already handles for llama.cpp and sd.cpp: pinned files, verified by sha256, run by a local server.
- **An OpenAI-style server.** `POST /v1/audio/speech` takes `model`, `input`, `voice` and `language` and returns `audio/wav`. `GET /health` and `GET /v1/models` answer as the other sidecars' do, and `POST /v1/tasks/unload_all_models` frees memory on request.
- **Source under Apache-2.0, released weekly.** v0.8.2, 24 Sep 2026, is the one measured here. The project is three months old; the apps that already run it are listed under [How others run it](#how-others-run-it).

Measured on a 12th-gen Core i5-1235U laptop, CPU, 6 threads, one model resident at a time, an 8-second English passage ([Measurements](#measurements)):

| Model | File | Output | Warm, per ~8 s of speech | Resident while voicing |
|---|---|---|---|---|
| Kokoro-82M, Q8_0 | 190 MB | 24 kHz | 5.9 s | 1.26 to 1.38 GB |
| Supertonic 3, F16 | 313 MB | 44.1 kHz | 4.3 s | 454 MB |
| KittenTTS Mini 0.8 | 302 MB | 24 kHz | about 5 s per 9.6 s | 1.02 GB |

All three voice faster than real time on a laptop CPU. A 15-minute podcast, the longest preset, takes roughly 8 to 12 minutes on this machine.

## Which models

A podcast gives each speaker a voice picked from a list, so a model the app curates must have **packaged voices** (no reference recording), **at least two** of them, weights that **allow commercial use**, and it must **run on a CPU** at about real time. Of audio.cpp's TTS families, three meet all four today:

| Model | Voices | Languages | Weights licence |
|---|---|---|---|
| **Kokoro-82M** | 54 packaged voices; 46 listed (below) | American and British English, Spanish, French, Hindi, Italian, Brazilian Portuguese, Mandarin | Apache-2.0 |
| **Supertonic 3** | 10: `M1` to `M5`, `F1` to `F5`, each in every language | 31, English and most of Europe among them | BigScience OpenRAIL-M, whose use restrictions are passed on |
| **KittenTTS Mini 0.8** | 8 | English | Apache-2.0 |

Manifest order is preference ([ADR 0026](../adr/0026-curated-order-is-list-position.md)): Kokoro first, because it has the most voices, and because its voice ids are the ones podcast briefs store today, so a returning user's last brief still validates once it is installed. Supertonic follows for its languages and its small memory, and Kitten as the smallest English-only choice.

Kokoro lists 46 of its 54 voices: its Japanese voices need MeCab and UniDic, which the release GGUF leaves out, and its three `*_santa` voices are novelty voices, left out as they are today.

Considered and not curated, each with its reason:

- **PocketTTS** (5 languages, CC-BY-4.0): each voice is a separate embedding file beside the GGUF, a multi-file build this work does not yet install. It joins when builds carry more than weights, the step FLUX needs too.
- **VibeVoice 1.5B** (MIT): true multi-speaker dialogue in one pass, but every speaker is a reference recording the app would have to ship. Its own step, below.
- **MagpieTTS 357M** (5 voices, 13 languages) and **Qwen3-TTS 1.7B CustomVoice**: 1.6 GB and 2.8 GB, not yet measured on a CPU.
- **NeuTTS 2E**: its licence allows commercial use only under USD 5M yearly revenue.
- **Piper**, **Chatterbox Turbo**, **Inflect**: one voice each.
- **sanoTTS**: GPL-3.0 weights.
- **Higgs Audio, BreezeTTS, OmniVoice**: non-commercial weights.
- **Voice design and cloning families** (Qwen3 VoiceDesign, MOSS-VoiceGenerator, IndexTTS2, CosyVoice3 and others): a voice from a description or a recording is a different podcast form, not a pick from a list.

## The runtime

`audiocpp_server --config <audio>/server.json`, started by Electron from the binaries directory with the eSpeak paths below.

The API writes `server.json` the way it writes llama.cpp's `models.ini` ([`preset.py`](../../surfsense_local/backend/modules/llm/providers/llamacpp/preset.py)): one entry per installed audio model, keyed by the build's id, naming its family, its file, `task: tts` and `mode: offline`. It rewrites the file after every install and delete and at startup, and Electron restarts the server on a change, as it does for the preset ([`runtime.md`](../architecture/local-models/runtime.md)).

The server-wide settings, each set because audio.cpp's default is wrong for this app:

| Setting | audio.cpp default | Here | Why |
|---|---|---|---|
| `backend` | `cuda` | `cpu`; `metal` on macOS if it measures faster | the GPU belongs to the chat model ([Backend](#backend)) |
| `threads` | 1 | half the logical cores, at most 8 | 1 thread nearly doubles the time; all cores add jitter ([Threads](#threads)) |
| `lazy_load` | false | true | nothing loads until a podcast asks |
| `max_loaded_models` | 0, no limit | 1 | one voice model resident at a time |
| `idle_unload_ms` | 0, never | 300000 | the backstop behind the explicit unload ([Residency](#residency)) |
| `min_free_memory_mb` | 0 | 1024 | a backstop: its estimate counts only the file it reads, so the app checks first ([Memory](#memory)) |

Measured behaviours the design rests on:

- **The server refuses an empty model list** ("server config requires a non-empty models array"), so Electron starts it only once the file names a model, and stops it when the last model is deleted.
- **It returns no voice list for these models.** `GET /v1/audio/voices` answered `[]` for all three, so each model's roster is committed in the manifest rather than read from the server.
- **Kokoro, Kitten and others phonemise through eSpeak-ng**, which audio.cpp loads at run time and does not ship; its maintainer confirms it has to be supplied ([audio.cpp#606](https://github.com/0xShug0/audio.cpp/issues/606)). Measured: with no eSpeak library found, the request fails, "eSpeak-ng library does not exist", and no audio is written. The sidecar is given `AUDIOCPP_ESPEAK_LIBRARY` and `AUDIOCPP_ESPEAK_DATA`, pointing at eSpeak files staged beside it: the same GPL-3.0 library and data the worker ships today inside `espeakng-loader`, taken from that package's pinned wheel for each platform, as Whispering Tiger does.
- **An unknown voice or model answers `500`**, not `400`, so the client checks a voice against the roster before it asks.

### Residency

The podcast drafts every segment with the chat model first, then voices every turn back to back. So:

- **The podcast job unloads the model when it ends**, with `POST /v1/tasks/unload_all_models`, success or failure. That is the moment the memory is known to be free to give back, and it does not depend on a timer.
- **`idle_unload_ms` of 5 minutes is the backstop** for a job that dies before it unloads. Five minutes is the common default: Ollama's `keep_alive`, Speaches' TTS and STT TTL, Unsloth Studio's speech-to-text sidecar, and most apps that drive audio.cpp.
- **The timer cannot cut into a podcast.** Measured, with a 5-second window: a single 20-second turn completed and left the model loaded, back-to-back turns kept it loaded, and the unload came only after 5 s of quiet. Every implementation read for this counts idle time from the end of the last request.
- **Memory comes back.** Measured, explicit or idle, the unload returns the model's memory to the operating system: Kokoro from 1.26 GB to 205 MB, Supertonic from 454 MB to 206 MB, Kitten from 1.02 GB to 273 MB. The 200 to 270 MB left is the server's own after its first model, released only when the process exits.
- **A reload costs a second or two.** Kokoro's cold request, load included, voiced 6.5 s of speech in 6.5 s, small beside the minutes a podcast takes. On the CPU there is no warm-up request, as Sokuji skips it off the GPU.

How much a model takes while it is loaded, and what the app does when that does not fit, is under [Memory](#memory).

### Memory

A loaded model's memory is mostly working space sized for one chunk of text, not its weights. Kokoro splits text into chunks of at most `text_chunk_size` characters, 240 by default, and its peak follows the chunk (measured, same passage, 6 threads):

| `text_chunk_size` | Kokoro's peak |
|---|---|
| 240, the default | 1,421 MB |
| 120 | 1,215 MB |
| 60 | 871 MB |

Nothing else moved it. Its graph arenas at a half, a quarter and an eighth of their defaults, `graph_capacity_mode` in all four values, `max_input_tokens` at 256, and glibc's `MALLOC_ARENA_MAX` at 2 and 1 each left the peak where it was, and the allocator limits made voicing 14 to 57% slower. A smaller chunk changes the audio, because each chunk is timed on its own.

So chunk size is the lever, and the app pulls it only when it must:

- **Before voicing, the app checks memory itself.** The server's `min_free_memory_mb` compares free memory with the bytes it will read from the file, 190 MB for Kokoro, not the 1.4 GB the model takes. The podcast job reads the operating system's available memory, as [`system_memory.available_bytes()`](../../surfsense_local/backend/modules/llm/hardware/system_memory.py) already does for fit, and compares it with the model's measured peak from the manifest plus 1 GiB of headroom.
- **Short of that, it steps the chunk down** (240, then 120, then 60), the way the chat catalog steps down to a smaller build before it refuses one.
- **Short even at the smallest chunk, it refuses**, with one sentence: "Voicing needs about 1.4 GB free; this computer has 0.9 GB." Only physics refuses, as for chat models ([ADR 0013](../adr/0013-fit-from-the-allocator.md)).
- **The server's `min_free_memory_mb` of 1024** stays as the backstop for a load the app did not check.
- **The adapter splits a long turn at sentence ends** before it asks, so a smaller chunk falls where a pause already is. A smaller chunk ships only after a listening test says it sounds right.

Kitten shares Kokoro's decoder design and likely the same dial; Supertonic takes 454 MB and does not need one. The upstream issue is narrow: memory grows by about 3 MB per chunk character, so could the decoder's buffers be sized to the chunk actually given?

### Threads

audio.cpp's server runs on one thread unless told otherwise. Measured, warm, the same passage:

| Threads | Kokoro | Supertonic |
|---|---|---|
| 1 (the default) | 10.8 s | 7.4 s |
| 4 | 6.5 s | 4.8 s |
| 6 (half the logical cores) | 5.9 s | 4.3 s |
| 10 (the physical cores) | 5.6 s | 3.9 s |
| 12 (every logical core) | 5.7 s | 4.3 s, and a 1.19× spread between runs |

Half the logical cores, at most 8, is what SubtitleEdit and yovoice use, reaches within 10% of the best here, and leaves cores to the chat model and the app. Every core is slower and noisier: ggml's workers spin while they wait, which Sokuji measured as a 2.55× run-to-run spread at all cores.

### Backend

The CPU on Windows and Linux. The GPU is the chat model's: llama-server keeps it resident, its fit estimate charges the one device it runs on ([ADR 0013](../adr/0013-fit-from-the-allocator.md)), and a podcast drafts with it right before voicing. A voice model on the same card would take memory that estimate never counted. Apps that run TTS next to an LLM place it the same way (Open WebUI, Open-LLM-VTuber, Home Assistant's Piper, SubtitleEdit, yovoice, LocalAI); SubtitleEdit stops its other engines before voicing because "typical user GPUs (8 GB) can fit at most one". audio.cpp calls CUDA its optimised path and CPU, Vulkan and Metal "intended for portability", and on this laptop's integrated GPU Vulkan made Kokoro slower (12 s against 6 s on the CPU).

On macOS too, until measured. Memory is one pool there either way, so Metal's only gain is speed, and its cost is sharing the GPU with the chat model, which llama.cpp runs on Metal. SubtitleEdit defaults to Metal, but runs no chat model beside it. Metal is used only if, on an Apple Silicon Mac, it is at least 1.3× faster warm for all three curated models and does not noticeably slow a chat answer given while a podcast voices, since the backend is set for the whole server.

### Packaging

The app compiles audio.cpp on Windows and Linux from a pinned commit, as Ollama compiles its llama.cpp backends and Jan now compiles its vendored llama.cpp, and takes upstream's archive on macOS. Nothing is hosted: a GitHub release on this repository would become the newest entry of the feed that installed apps read for updates ([updates](../architecture/updates.md)). Upstream's Windows and Linux archives each fail one of the app's floors:

- **Linux: glibc.** Every v0.8.2 Linux archive needs glibc 2.38 (Ubuntu 24.04); the app holds 2.34 (Ubuntu 22.04) for its AppImage.
- **Windows: the CPU.** The Vulkan archive has no per-CPU libraries: its CPU code is inside `audiocpp_server.exe`, which carries about 7,300 AVX-512 instructions, so it would stop with an illegal instruction on the Intel 12th to 14th generation and AMD before Zen 4.
- **macOS** takes `audio-<tag>-bin-macos-arm64-metal.tar.gz` (28.4 MB for v0.8.2); there is no Intel Mac build ([ADR 0021](../adr/0021-no-intel-mac-build.md)).

`scripts/audiocpp/stage.mjs` stages the server, its ggml libraries, the curated families' `model_specs/`, its licence and eSpeak, in dev as `pnpm build:audiocpp` and in the release, and signing and notarization cover them as they do `sd-server`. Its recipe, `scripts/audiocpp/recipe.mjs`:

- builds the CPU backend only, since the server runs with `--backend cpu`. A Vulkan build was 329 of 836 build steps and 57 to 58 MB of each package, and ggml loaded it at start regardless;
- builds one ggml CPU library per micro-architecture, picked at start, and only the curated families;
- turns OpenMP off, as upstream's macOS builds do, so ggml's own thread pool runs and no `libgomp` ships; the thread sweep is repeated to confirm it is not slower;
- on Linux links libstdc++ statically into every file, ggml's CPU modules included, since audio.cpp requires GCC 13 and 22.04's own C++ runtime is older. libgcc stays dynamic: GCC 12 and 13's static unwinder on 22.04 calls `_dl_find_object`, from glibc 2.35, measured on the runner.

In release CI, [`build-audiocpp.yml`](../../.github/workflows/build-audiocpp.yml) compiles on `ubuntu-22.04` and Windows, gates the Linux build on `objdump -T` naming nothing newer than `GLIBC_2.34` or `GCC_7.0.0`, RHEL 9's, and on no file needing libstdc++, libgomp or Vulkan, voices one Kokoro passage on both, and hands the staged folders to the packaging jobs. It caches by the recipe, so most releases do not compile. A developer compiles once, with CMake and GCC 13 or Visual Studio 2022; without them `pnpm dev` runs without local audio.

This is a stopgap. Step 1 opens an issue upstream asking for a Windows archive with per-CPU libraries and a Linux archive built on 22.04; when both exist, the app downloads them as it does llama.cpp's, and the compile path goes.

## The catalog slice

`catalog/local/engines/audiocpp/`, beside [`llamacpp/`](../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/) and [`sdcpp/`](../../surfsense_local/backend/modules/llm/catalog/local/engines/sdcpp/), grouped the same way:

| Part | What it holds |
|---|---|
| `evidence.py` | a file's family, read from its header |
| `manifest_fields.py` | the `audio` block every audio entry requires |
| `builds/` | which files make a build (one GGUF each), and each model's default build |
| `rows/` | the manifest's audio models and the audio folder as rows, unpriced like image rows |
| `audio_folder/` | its files, the installed model, and `server.json` |
| `engine.py` | the adapter: `after_install` and `after_remove` rewrite `server.json`, `on_startup` writes it |

**Evidence.** Every audio.cpp GGUF declares `general.architecture = audiocpp`; the family is `audiocpp.model_spec.family` (`kokoro_tts`, `supertonic`, `kitten_tts`). The classifier listed `audiocpp` among speech recognisers, so a searched text-to-speech repo read "writes down what it hears". The family becomes the evidence's architecture, and the voice families join the text-to-speech group, `AUDIO_GEN`. A bare `audiocpp`, which speech recognisers declare too, gets its own typeless group: "This model runs on audio.cpp. SurfSense runs only the voices in its list." Kokoro's header embeds its voice packs, 38.6 MB of metadata, and Supertonic's runs to 57 MB, past the 24 MiB the header reader widens to, so the refresh script reads the first 64 KiB and walks the keys in order to the family, the seventh key in all three files.

**The `audio` block**, reviewed like `image`:

```jsonc
"audio": {
  "origin": "hexgrad/Kokoro-82M model card; memory measured on audio.cpp v0.8.2, 24 Sep 2026",
  "sample_rate": 24000,
  "peak_mb": 1421,                                   // at the server's default text_chunk_size; the screen states it
  "chunk_steps": [                                   // smaller chunks and their peaks, where one was measured
    { "text_chunk_size": 120, "peak_mb": 1215 },
    { "text_chunk_size": 60, "peak_mb": 871 }
  ],
  "languages": ["en-GB", "en-US", "es", "fr", "hi", "it", "pt-BR", "zh"],
  "voices": [
    { "id": "af_heart", "label": "Heart", "language": "en-US" },
    { "id": "bm_fable", "label": "Fable", "language": "en-GB" }
    // …; a voice with no language speaks every language in `languages` (Supertonic)
  ]
}
```

Supertonic has no chunk setting, so it commits a peak and no steps; Kitten commits its peak until its chunk sweep is measured. The schema refuses a model with fewer than two voices, a repeated voice id, and a voice in a language the model does not list. Kokoro's Mandarin voices are listed: audio.cpp phonemises Mandarin with its own Jieba and pinyin front end, not eSpeak, the reason the worker's Kokoro left them out.

**Builds.** One GGUF each, from the model's own folder of `audio-cpp/audio.cpp-gguf`, pinned like every build; the entry lists them most preferred first, and the first is the default. The defaults are Kokoro `Q8_0` (190 MB; `BF16` is the other build), Supertonic `F16` (313 MB; its `q8_0` file has the `orig` file's hash, so only `orig` is pinned beside it) and Kitten's only build, `orig` (302 MB). `orig` is audio.cpp's name for source precision. All three models share the repo, and two have an `orig` build, so an install is matched by its recorded file, not by repo and label. `refresh_local_manifest.py --only` adds them without re-pinning the other entries. LocalAI reports Supertonic's F16 file aborting inside ggml and uses the 454 MB full-precision one; F16 ran here on the CPU, so it is checked on every platform before it ships, with the full-precision file as the fallback. Audio rows carry no fit estimate, as image rows do not; they state the memory measured while voicing instead, and the podcast checks it before it starts ([Memory](#memory)).

## Selection and Studio

- **A selection.** `audio_gen` takes provider `audiocpp`, with no connection. A hand-written revision rebuilds `selected_models`' checks, as [`0013`](../../surfsense_local/backend/alembic/versions/0013_selection_by_model_type.py) did, so `audiocpp` is allowed only for `audio_gen`. Onboarding does not ask for one, as it does not ask for an image model.
- **The screen.** A third section, **Audio**, headed **Audio generation models**, beside Chat and Image ([`features/models/`](../../surfsense_local/frontend/src/features/models/)): the model in use, the ones on this computer with Use and Delete, and Add model with the curated rows, each showing its size, the memory it takes while voicing, its voice count and its languages. It shows the catalog only when the API reports the audio folder, which Electron sets when it staged the server.
- **The podcast.** Its required model types become `text_gen` and `audio_gen`, in place of the `requires_voice` flag. `resolve_text_to_speech()` reads the `audio_gen` selection and returns an adapter in `providers/audiocpp/`: its `voices()` are the installed model's roster, `synthesize()` asks the server for each turn and joins the WAVs with the 0.35 s gap used today, and the job unloads the model when it ends. The brief's language list and voice picker come from the roster; a remembered brief whose voices the new model lacks falls back to the proposed one, as it does today.
- **Remote audio stays out.** A connection's model can already be selected for `audio_gen`, but nothing here calls a remote speech endpoint, so the podcast says so and stays unavailable until a remote speech client exists.

## What goes

[`providers/kokoro/`](../../surfsense_local/backend/modules/llm/providers/kokoro/), [`scripts/fetch_kokoro_model.py`](../../surfsense_local/backend/scripts/fetch_kokoro_model.py), the `build:voice` script, `kokoro-onnx`, and `kokoro_onnx`, `espeakng_loader` and `phonemizer` from [`worker.spec`](../../surfsense_local/backend/bundling/worker.spec). onnxruntime stays for the retrieval model. Podcasts already made keep their audio: an artifact stores its WAV.

## Order of work

Each step ships alone and leaves the app working.

1. **The runtime, built and staged.** The Windows and Linux compile in release CI, `scripts/audiocpp/` with eSpeak, the sidecar spec, and Electron's watcher of `server.json`. Nothing writes the file yet, so nothing starts.
2. **The catalog slice.** Evidence and the classifier fix, the `audio` block, the three entries through the refresh script, rows, installs into the audio folder, and `server.json`.
3. **Selection and the screen.** The revision, `audio_gen` through `audiocpp`, and the Audio section.
4. **The podcast on audio.cpp.** The adapter, the unload at the end of a job, the podcast's model types, and its brief from the roster; the Python Kokoro removed; the README, `studio.md`, `packaging.md` and `overview.md` updated.
5. **Later, each its own step:** VibeVoice, with reference voices the app ships; PocketTTS, once builds carry voice files; Magpie and Qwen3 CustomVoice, after a CPU measurement; audio models from Hugging Face search; a remote speech client; a memory estimate.

## How others run it

audio.cpp is young, and the apps that drive its server are few; these are the ones whose settings informed the table above ([research, 24 Sep 2026](https://github.com/0xShug0/audio.cpp#projects)):

| App | Load | Resident | Unload | Threads | Backend | Binary |
|---|---|---|---|---|---|---|
| [SubtitleEdit](https://github.com/SubtitleEdit/subtitleedit/blob/main/src/ui/Features/Video/TextToSpeech/Engines/FishTtsAudioCpp.cs) | lazy | one engine | kills the server: "audio.cpp never unloads a model on its own once loaded" | logical/2, at most 8 | CPU, Metal on macOS | builds its own |
| [Whispering Tiger](https://github.com/Sharrnah/whispering/blob/main/Models/audio_cpp_runtime.py) | lazy | 1 | none | every core | user's choice | pinned upstream archive; eSpeak from the `espeakng_loader` wheel |
| [VoiceStudio](https://github.com/debpalash/VoiceStudio/blob/main/backend/engines/audiocpp/__init__.py) | lazy | 1 | `unload_all_models`, then kills | physical cores, at most 16 | best available | pinned upstream archive |
| [yovoice](https://github.com/leemysw/yovoice/blob/main/internal/workbench/engine.go) | lazy | 1 | idle, 5 min | logical/2, at most 8 | CPU | pinned upstream archive, eSpeak through the same variables |
| [pithagoras](https://github.com/thecodacus/pithagoras/blob/HEAD/docs/guide/voice.md) | lazy | 1 | idle, 90 s | 4 | CUDA | builds its own |
| [LocalAI](https://github.com/mudler/LocalAI/blob/master/docs/content/features/audio-cpp.md) | in process | one per process | its watchdog, off by default | runtime's choice | CPU | builds its own |
| [Sokuji](https://github.com/kizuna-ai-lab/sokuji/blob/main/native/include/sokuji_native.h) | in process | per session | when the session closes | at most 12, measured | CPU, Vulkan or Metal | static |

And for the timeout, beyond audio.cpp: Ollama keeps a model 5 minutes after its last request, Speaches 5 minutes for TTS, LocalAI 15 minutes when its watchdog is on, LM Studio 60 minutes; llama.cpp's server, Kokoro-FastAPI and llama-swap never unload by default. None unloads during a request.

## Decided here

- audio.cpp's server is the one local audio runtime. The app compiles it, CPU-only, on Windows and Linux from a pinned commit, and takes upstream's archive on macOS, pinned by sha256. Nothing is published as a release of this repository.
- Audio models are downloaded, not bundled; nothing voices a podcast until one is installed and chosen.
- Kokoro-82M, Supertonic 3 and KittenTTS Mini are curated, in that order. A curated audio model has packaged voices, at least two, commercial-use weights, and runs on a CPU at about real time.
- A model's voices and the memory it takes while voicing are committed in the manifest, because the server lists neither.
- One audio model is resident at a time, loaded on first use, unloaded by the podcast job when it ends, and unloaded after 5 idle minutes otherwise.
- The server runs on the CPU with half the logical cores, at most 8, and without OpenMP; Metal on macOS only on the rule under [Backend](#backend).
- The podcast checks memory against the model's measured peak before voicing, steps Kokoro's chunk size down before it refuses, and refuses only when the smallest chunk will not fit. The server's `min_free_memory_mb` of 1024 is a backstop.
- The Python Kokoro and its packages leave the worker.
- The podcast reads local audio models only until a remote speech client exists.

## Open questions

Each is a measurement with its rule already set above:

- **Metal on an Apple Silicon Mac**: warm and cold for the three models, and a chat answer's time while a podcast voices. Metal if it clears the bar under [Backend](#backend); the CPU otherwise.
- **Kokoro at chunk 120 and 60**: a listening test on podcast turns split at sentence ends. A size that fails it is not stepped down to.
- **Kitten's chunk size**: the same sweep as Kokoro's, to see whether it has the same dial.

## Measurements

24 Sep 2026, audio.cpp v0.8.2 (`audio-v0.8.2-bin-ubuntu-x64-vulkan.tar.gz`), Linux, 12th Gen Intel Core i5-1235U (10 cores, 12 threads), Intel Iris Xe (integrated). One server with the three models, `lazy_load` and `max_loaded_models: 1`. Text: "Welcome back to the show. Today we are talking about how a small model can read a whole document aloud, on your own laptop." Times are end-to-end `POST /v1/audio/speech`; a cold request includes the model's load. The first series ran at 4 threads, before the thread sweep above.

| Model | Voice | Backend | Cold | Warm | Audio | Resident |
|---|---|---|---|---|---|---|
| Kokoro Q8_0 | `af_heart` | CPU, 4 threads | 12.3 s | 4.3 to 7.7 s | 7.75 s | 1.45 GB |
| Kokoro Q8_0 | `bm_fable` | CPU, 4 threads | 7.6 s | 7.5 s | 7.35 s | 1.44 GB |
| Supertonic 3 F16 | `M1` | CPU, 4 threads | 11.2 s | 6.9 s | 8.09 s | 452 MB |
| Supertonic 3 F16 | `F2` | CPU, 4 threads | 5.9 s | 6.1 s | 7.59 s | 454 MB |
| KittenTTS Mini 0.8 | `Leo` | CPU, 4 threads | 9.1 s | 8.4 s | 9.69 s | 1.03 GB |
| KittenTTS Mini 0.8 | `Bella` | CPU, 4 threads | 7.8 s | 8.2 s | 8.94 s | 1.03 GB |
| Kokoro Q8_0 | `af_heart` | Vulkan | 24.4 s | 12.1 to 12.8 s | 7.75 s | |
| Supertonic 3 F16 | `M1` | Vulkan | 17.7 s | 1.4 to 6.7 s | 8.09 s | |

Unloading, 6 threads, `idle_unload_ms: 5000`. Server memory at start: 13 MB.

| Model | Loaded | After `unload_all_models` | Reload, cold | After the idle window |
|---|---|---|---|---|
| Kokoro | 1,255 MB | 205 MB | 6.5 s, 1,375 MB | 205 MB |
| Supertonic | 454 MB | 206 MB | 6.1 s, 454 MB | 206 MB |
| Kitten | 1,023 MB | 273 MB | 5.5 s, 1,023 MB | 273 MB |

The system's available memory rose by about the same amounts after each unload. A 26.8-second passage took 20.1 s and completed with the model still loaded, though the window was 5 s.

Memory against settings, Kokoro through the CLI, 6 threads, `--seed 7`, peak resident memory:

| Setting | Peak | Audio |
|---|---|---|
| defaults (`text_chunk_size` 240) | 1,421 MB | reference |
| predictor arenas at 1/2, 1/4, 1/8 of their defaults | 1,566 MB each (4 threads) | byte-identical |
| `graph_capacity_mode` `fixed`, `tiered`, `grow`, `double` | 1,421 MB each | byte-identical |
| `max_input_tokens` 256 | 1,421 MB | byte-identical |
| `text_chunk_size` 120 | 1,215 MB | differs |
| `text_chunk_size` 60 | 871 MB | differs |

And through the server, peak after three requests: Kokoro 1,449 MB, Kitten 1,011 MB, Supertonic 368 MB with glibc's defaults; within 2% of those with `MALLOC_ARENA_MAX` at 2 or 1, and 14 to 57% slower.

The CPU numbers vary from run to run on this laptop, by as much as 50% for the same request; read them as the order of magnitude, not a benchmark.

The app's own builds, 24 Sep 2026, test runs of `build-audiocpp.yml`, v0.8.2 with the three curated families. The Vulkan builds came first and were dropped:

| | Linux x64 | Windows x64 |
|---|---|---|
| Compile, CPU only | 3.6 min | 9.5 min |
| Compile, with Vulkan | 9.1 min | about 11.5 min |
| Staged folder, CPU only, eSpeak included | 50.0 MB | 33.0 MB |
| ggml's Vulkan library, no longer built | 59.9 MB | 57.5 MB |

The Linux build passed the gate: nothing newer than `GLIBC_2.34` or `GCC_7.0.0`, and no file needing libstdc++, libgomp or Vulkan. The Windows server has no AVX-512 instructions, against 7,264 in upstream's; that code now sits only in `ggml-cpu-skylakex.dll`, which ggml loads only on a CPU that has it. Both voiced a Kokoro passage in CI with the sidecar's eSpeak paths and flags. Staged on the laptop above with those flags, the earlier Linux build voiced each curated model, the model's load included, in 3 to 5 seconds.
