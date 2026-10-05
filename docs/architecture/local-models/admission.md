# Admission and parallel slots

The local runtime serves up to four replies at once from one shared cache, and every request that generates on it is admitted first, by one gate in the API. Remote models are never admitted: each provider has its own servers.

**Code:** [`modules/llm/admission/`](../../../surfsense_local/backend/modules/llm/admission/), [`modules/llm/model_route/`](../../../surfsense_local/backend/modules/llm/model_route/), [`modules/llm/fit/plan_load.py`](../../../surfsense_local/backend/modules/llm/fit/plan_load.py), [`providers/llamacpp/preset.py`](../../../surfsense_local/backend/modules/llm/providers/llamacpp/preset.py)
**Decisions:** [ADR 0039](../../adr/0039-the-api-is-the-only-path-to-a-text-model.md), [ADR 0011](../../adr/0011-llama-cpp-local-runtime.md)

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

## Known gaps

- Studio's image and audio calls still reach their servers directly, so the worker keeps the key-decryption secret for remote ones.
- Admission counts the cache, not the speed: four replies decoding together each run slower than one alone.
