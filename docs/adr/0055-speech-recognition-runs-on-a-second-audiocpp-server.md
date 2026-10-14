# ADR 0055: Speech recognition runs on a second audio.cpp server that only the API calls

- **Status:** Proposed, with the [local speech recognition proposal](../proposals/local-speech-to-text.md)
- **Date:** 2026-10-14
- **Source:** [Local speech recognition proposal, the runtime L119–147](https://github.com/MODSetter/SurfSense/blob/55b3ddc2e9d6423f194ff7e5ef0c62910cece95f/docs/proposals/local-speech-to-text.md#L119-L147)

## Context

Recordings as sources and a mic in the chat composer need a speech recogniser that runs on the user's CPU and takes as little of the machine as it can. The app already ships audio.cpp's `audiocpp_server` for podcast voices ([packaging](../architecture/packaging.md)), and its pinned v0.8.2 source has NVIDIA's Nemotron 3.5 ASR, which held 1.19 GB loaded and ran at 11.5× real time on that server's CPU path. Compiling its family adds 9 source files and no new library.

The voices' server cannot also serve it. Under its flags a dictation would evict Kokoro between a podcast's turns; a request that finds the other model busy fails at once with 503; the podcast's closing `unload_all_models` would unload a warm speech model and wait without bound on a transcription in flight; and every voice install, delete and API start rewrites `server.json`, which restarts the server and kills whatever it is transcribing.

Text models already reach their runtime only through the API, so one gate can order every request ([ADR 0048](0048-the-api-is-the-only-path-to-a-text-model.md)). A recording's windows from the ingest worker and a speaker's phrases from the composer compete for one model the same way.

## Decision

- Speech recognition runs on `audiocpp_server`, the binary staged for voices, compiled with `nemotron_asr` beside the voice families and started a second time as its own sidecar, `audiocpp-transcription`.
- It reads its own config, `<data>/audio/transcription.json`, which the API writes, and listens on its own port. Electron passes the flags: the CPU backend, half the logical cores up to 8, one loaded model, an unload after 5 idle minutes, 1 GiB kept free, no web UI. It gets no eSpeak.
- Electron starts it when that file exists, restarts it when the file changes and stops it when the file goes. After a crash it restarts it, at most once every 10 seconds, and leaves it stopped after 3 crashes in 5 minutes, until the file changes again.
- Only the API is told where it is. Every other process reaches speech recognition through the API.
- One gate in the API sends every request to it, one at a time, since it runs one model and one request at a time anyway. A dictation's phrase goes ahead of a recording's window and waits at most for the window in flight. While a dictation is open, from the mic press until its last phrase or 20 s without one, no window starts.
- A hold of the text runtime, which a podcast takes while it voices and a local image while it draws, also starts no window until it ends, waits for the request in flight, and unloads the speech model by id. Dictation stays available during it, behind the memory check.
- Before a request that would load the model, the API checks the entry's measured peak plus 1 GiB against the memory the operating system says is available, unless the server says the model is loaded. Speech never unloads or holds the chat model; a shortfall is refused in a sentence.
- [transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) is the fallback, replacing the API's client, the sidecar spec and the config writer, not the routes.

## Consequences

- Voices and speech recognition never unload, evict, restart or wait on each other. The second process costs 7 MiB idle and 10 MiB after its model is unloaded (measured).
- A dictation does not wait for a recording behind the server's own queue, because the API decides the order. A recording pauses while someone dictates, and while a podcast voices or an image draws.
- The server's own memory guard, which estimates from the file's size, is only a backstop: the app admits from a measured peak.
- The languages are those of the families in the pin. audio.cpp will not run Whisper, so the long tail of languages needs a later model or the fallback.
- One binary serves both, so a pin bump is measured for both: the voices' peaks and the speech model's.
- Settings › Resources counts the second process under its audio.cpp row with no change, since it counts every `audiocpp_server`.

## Where the code stands

The family is compiled and checked in staging, and Electron has the sidecar, its watcher with the crash restart, and the API's address (`sidecars/audiocpp-transcription.ts`, `sidecars/watch-transcription-models.ts`, `sidecars/python.ts`). The API writes `transcription.json` once a speech recogniser is downloaded, so the server runs only then. Its client (`providers/audiocpp/transcription.py`, behind the `Transcriber` protocol), the gate and the dictation and windows routes are in `modules/llm/transcription/` ([admission](../architecture/local-models/admission.md#speech-recognition)); no screen or ingest job calls them yet ([proposal](../proposals/local-speech-to-text.md#order-of-work), steps 5 and 7).
