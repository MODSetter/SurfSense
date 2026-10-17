# Admission and parallel slots

The local runtime serves up to four replies at once from one shared cache, and every request that generates on it is admitted first, by one gate in the API. Remote models are never admitted: each provider has its own servers. Speech recognition has a gate of its own, for the one request its server runs at a time ([below](#speech-recognition)).

**Code:** [`modules/llm/admission/`](../../../surfsense_local/backend/modules/llm/admission/), [`modules/llm/model_route/`](../../../surfsense_local/backend/modules/llm/model_route/), [`modules/llm/fit/plan_load.py`](../../../surfsense_local/backend/modules/llm/fit/plan_load.py), [`providers/llamacpp/preset.py`](../../../surfsense_local/backend/modules/llm/providers/llamacpp/preset.py), [`modules/llm/transcription/`](../../../surfsense_local/backend/modules/llm/transcription/)
**Decisions:** [ADR 0048](../../adr/0048-the-api-is-the-only-path-to-a-text-model.md), [ADR 0011](../../adr/0011-llama-cpp-local-runtime.md), [ADR 0056](../../adr/0056-speech-recognition-runs-on-a-second-audiocpp-server.md)

## Slots

The preset ([runtime](runtime.md#the-preset-file)) writes `parallel = N` from the load plan, and `kv-unified = on` above one slot: one cache the size of the window, shared by every slot, so a reply alone keeps the whole window. At `b11050`, `/props` on a model loaded with `-np 4 -kvu -c 4096` reports `total_slots: 4` and `n_ctx: 4096`, and the log says `n_slots = 4, n_ctx_slot = 4096, kv_unified = 'true'`: each slot is told it has the whole window.

`plan_load()` chooses N with `planned_slots()`, the one rule the load and the catalog's badge share ([fit](fit.md#the-load-plan)):

1. Ask for four.
2. On unified memory keep four: its free-memory reading is the least reliable figure the plan has, and `--fit` spills rather than fails.
3. Elsewhere, take the most slots, from four down to one, that keep the model resident at the 8,192 floor; where none would, keep four, since cutting slots cannot rescue a load that spills anyway.
4. Widen the window as far as that count stays resident.

What slots cost is llama.cpp's own arithmetic. A sliding layer holds `n_swa × slots + n_ubatch` cells, so a sliding-window model pays per slot: Gemma 3 4B's cache at 16,384 is 752 MiB at one slot and 1,232 MiB at four. A layer that attends to the whole window holds the window whatever the count, so Qwen3 pays nothing. The output rows of the compute buffer grow by one per slot.

Against the curated catalog that moves only sliding-window models on tight machines. On an 8 GB Mac, 9 of 126 builds change: Gemma 3 4B's windows halve, its recommended build from 16,384 to 8,192, and its Q6_K goes from resident to a partial spill. On a 6 GB card 6 builds change the same way. 16 GB machines and machines without a GPU see no change.

## Admission

One pool per loaded model, because in router mode each is its own child with its own cache ([`local_runtime.py`](../../../surfsense_local/backend/modules/llm/admission/local_runtime.py)). A pool's slots and token budget are what `/props` reports for the model, read again whenever the pool is idle; a model not loaded yet counts as one slot of unknown size.

- **The rule** ([`pool.py`](../../../surfsense_local/backend/modules/llm/admission/pool.py)): a request is admitted when a slot is free and the tokens already committed plus its cost fit the budget. When nothing runs it is admitted regardless: the window, not admission, refuses an oversize prompt.
- **Cost** ([`cost.py`](../../../surfsense_local/backend/modules/llm/admission/cost.py)) is worked out by the API from the request, never declared by the caller: the prompt at three Latin characters or one other character a token, which errs high where the chat budget's four a token undercounts Chinese, Japanese and Korean; 1,400 per image; and `max_tokens`, or 1,024 kept within a fair share of the budget when the request states none.
- **Order:** interactive work (chat replies, titles, agent steps) ahead of background work (Studio). Within a class, strictly first come, first served: the head of the line is never overtaken by a smaller request. A running request is never pre-empted, and Studio has no ageing.
- **Release** when the generation ends, fails, is stopped or its caller disconnects; one that leaves while waiting leaves the line. The line holds at most 64 per pool.
- **Where it is taken.** In process for the API's own calls ([chat](../chat.md#the-stream)); in the agent's model endpoint per step, so a growing tool loop is priced afresh every step and holds no room while opencode runs a tool; and in the model route for every other process.
- A queued chat reply sends `run-state: queued` with its place, and the thread says "Waiting for another reply". A Studio job stays `processing`.

## The model route

`POST /internal/models/text/generate` is how any process other than the API generates text ([`model_route/router.py`](../../../surfsense_local/backend/modules/llm/model_route/router.py)). The body is what `Generator.chat` takes, plus `model` (`{provider, name, connection_id}`, or left out for the current selection) and `priority` (`background`).

- The API resolves the named model, so a Studio job keeps the model it started with even if the selection changes; one that can no longer be resolved, deleted or with its connection gone, or a local one the runtime no longer lists, is `409`. It checks egress, marks the model in use and admits a local request.
- The reply streams as `data:` frames: `queued` with the place in line while it waits, `text` per chunk of the answer, `error` on a failure, then `[DONE]`. A `: keep-alive` comment goes out after any 15 quiet seconds, so a request waiting behind chats, or a model reading a long prompt, never looks dead.
- Failures cross as frames the worker raises again as the same type ([`failures.py`](../../../surfsense_local/backend/modules/llm/model_route/failures.py)): `httpx.HTTPStatusError` with its status, `StreamTimeoutError`, `SignInRequiredError`, `PlanLimitError`, `EgressDeniedError`, `ModelResolutionError`, and an unreachable host as a network error.
- Studio's text model resolves to `RoutedGenerator` for every text model, local and remote ([`model_route/client.py`](../../../surfsense_local/backend/modules/llm/model_route/client.py)), at the API address every Python sidecar is handed. The provider's own start and stall budgets run in the API; the worker only gives up on a connection silent for 60 seconds, so waiting in line never trips the 300-second start timeout a direct call has.
- A caller that disconnects leaves the line or closes the provider's stream.

## The image job's hold

Before a local image is drawn, the text models leave the graphics card. `POST /internal/models/text/yield`, held open by the Studio worker for the whole image ([`runtime_hold.py`](../../../surfsense_local/backend/modules/llm/model_route/runtime_hold.py)), pauses every pool, waits for running generations to finish, unloads every loaded text model, then answers `yielded`. Local text sent meanwhile waits in line; when the worker closes the request, or dies and drops it, the pools resume and the router loads the chat model again on its next request.

The same hold, which a podcast also takes while it voices, pauses speech recognition's recordings: no new window starts, the one in flight finishes, then the speech model is unloaded by id before `yielded` is sent. Dictation goes on during the hold, behind the memory check, and its phrases share the CPU with the voicing ([below](#speech-recognition)).

## Speech recognition

The transcription server, audio.cpp run a second time, holds one model and runs one request at a time, and only the API reaches it ([ADR 0056](../../adr/0056-speech-recognition-runs-on-a-second-audiocpp-server.md)). Every request goes through one gate, [`gate.py`](../../../surfsense_local/backend/modules/llm/transcription/gate.py), so a speaker never waits behind a recording.

- **Dictation first.** A phrase waits at most for the request in flight, a recording's window of up to 28 s: about 2.5 s at the measured 11.5x real time. No window starts while a phrase waits.
- **An open dictation holds the server.** From `POST /llm/transcription/dictations` until its `DELETE`, 20 s without a phrase or keepalive, or 6 minutes ([`sessions.py`](../../../surfsense_local/backend/modules/llm/transcription/sessions.py)), no window starts. Opening one ends any other; phrases already sent for it still answer, and later ones are `404 dictation_ended`.
- **A window waits at most 30 s** at `POST /internal/transcription/windows`, the ingest worker's route, then answers `503` with the code `waiting` and its reason: `dictation`, `hold`, `memory` with both sizes, or `busy` behind another window. The worker asks again.
- **Memory** ([`memory_admission.py`](../../../surfsense_local/backend/modules/llm/transcription/memory_admission.py)). Before a request that would load the model, the server's `GET /v1/models` is read: a model already `loaded` needs no check, since the operating system's figure leaves it out. Otherwise the entry's measured `peak_mb` plus 1 GiB must be available, the podcast's rule ([studio](../studio.md#voicing-a-podcast)). Opening a dictation or sending a phrase short of it is `409 transcription_needs_memory`, with `needed_bytes`, `available_bytes` and the sentence: "Transcribing needs about 2.9 GB free; this computer has 1.8 GB." A window short of it waits off the gate, looking again every 5 s, so no phrase waits behind it. Speech never unloads or holds the chat model: reloading one costs 10 to 26 s, and dictated text is about to go to it.
- **Residency.** Opening a dictation sends an unloaded model 0.5 s of silence, so it loads while the speaker starts. A recording's last window, sent with `last`, unloads the model by id unless a dictation is open, as the podcast does when it ends. The hold above unloads it too. The server's 5-minute idle unload is the backstop.
- **Each request** ([`providers/audiocpp/transcription.py`](../../../surfsense_local/backend/modules/llm/providers/audiocpp/transcription.py), behind the `Transcriber` protocol) is the clip as a WAV from memory, multipart to `/v1/audio/transcriptions/details`, with the model's id and the language's locale, or none to detect it. Its deadline is the longer of 120 s and 20 times the audio's length, so a hung server fails one window, not the job. A refused or dropped connection, or a `503`, as while the server restarts, is asked once more after 2 s; then the route answers `503 transcription_unavailable`, as it does at once for a request past its deadline or a reply with no text to read. The request holds the model in use ([`activity.py`](../../../surfsense_local/backend/modules/llm/activity.py)), so a delete during it is refused, and a phrase after the model is deleted ends its dictation with `409 needs_speech_model`.
- **A phrase** is a 16 kHz mono 16-bit WAV of at most 30 s, checked with the standard library (`422 unfit_audio` otherwise). Silero VAD ([`voice_activity/`](../../../surfsense_local/backend/modules/llm/transcription/voice_activity/)), on the onnxruntime already in the API and on one thread, answers `no_speech` for under 250 ms of speech without asking the model. The text loses Nemotron's locale tags, the last of which names the language; a sentence with no closing punctuation comes back untagged, as French and Hindi did in the packaging test, and then the language is the one the user set, or under auto the one a script names when only one listed language writes it (Devanagari, Han, kana, Hangul, Arabic), else none ([`languages.py`](../../../surfsense_local/backend/modules/llm/transcription/languages.py)). It then goes through the cleanup the [proposal](../../proposals/local-speech-to-text.md#audio-files-as-sources) sets, which also joins a comma or full stop written apart from its word, as Canary writes German ([`cleanup.py`](../../../surfsense_local/backend/modules/llm/transcription/cleanup.py)). `GET /llm/transcription/status` says whether dictation can start: `ready`, or `needs_speech_model` or `transcription_unavailable`.

## Known gaps

- Studio's image and audio calls still reach their servers directly, so the worker keeps the key-decryption secret for remote ones.
- Admission counts the cache, not the speed: four replies decoding together each run slower than one alone.
