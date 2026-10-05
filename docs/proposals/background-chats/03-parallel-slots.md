# Parallel slots

llama-server decodes several requests at once when it has more than one slot. With `--kv-unified` the slots share one cache the size of the window rather than splitting it, so a single reply keeps the whole window and parallelism costs little memory. Admission ([`02-admission.md`](02-admission.md)) is what keeps the shared cache from overflowing.

## The preset

The preset ([runtime](../../architecture/local-models/runtime.md), The preset file) writes `parallel = N` from the load plan and, when N is above 1, `kv-unified = on`. `b11050` has both: `-np, --parallel N` and `-kvu, --kv-unified`, whose default is on only when the slot count is automatic. Nothing else in the preset changes.

## Choosing N

`plan_load()` ([fit](../../architecture/local-models/fit.md), The load plan) asks for four slots on every backend and keeps residency first:

1. **Plan for four slots.** The window widens over `CONTEXT_RUNGS` (8,192, 16,384, 32,768) while the model stays resident with four slots, as it widens for one slot today.
2. **If four slots are not resident even at 8,192,** try 3, then 2, then 1, each priced at 8,192, and keep the first count that is resident.
3. **Then widen the window** as far as that count stays resident.
4. **If not even one slot is resident at 8,192,** keep four. The model spills as a `PARTIAL` build does today, and `--fit` places what does not fit on the CPU.
5. **On Metal, slots are not reduced.** The load keeps four, and the window is planned at four.

Why this order:

- **Residency comes first, as it does today.** A layer spilled to the CPU slows every reply, including a lone one, by more than any slot count costs. Slots are cut only to avoid a spill.
- **Slots are priced at the floor, not the planned window.** The question at step 2 is whether a slot count can run resident at all. Pricing it at a wider window would cut slots that run fine at a narrower one, and the window search after it gives back whatever memory the slots leave.
- **A model that spills anyway keeps its slots.** Cutting slots cannot make it resident, and for a model without sliding layers extra slots cost almost nothing under a unified cache.
- **Metal is not reduced on the estimate.** Apple silicon shares its memory with the system, and the free memory the plan reads there is the least reliable figure it has ([fit](../../architecture/local-models/fit.md)), so slots are not traded on it. `--fit` spills rather than fails if the load does not fit.

The trade this accepts: on a tight machine with a sliding-window model, four slots can hold the window at 8,192 where one slot would reach 16,384. History then gets roughly 3,300 tokens a turn instead of 11,500 (a turn spends about 4,800 before history: system prompt 400, excerpts 2,400, question 1,024, answer 1,024; [`budget.py`](../../../surfsense_local/backend/modules/chat/budget.py)), even for a chat running alone. A model without sliding layers is not affected.

## What slots cost

- **Cache, sliding-window layers only.** A sliding layer holds `n_swa × slots + ubatch` cells; a layer that attends to the whole window holds the window, whatever the slot count. For Gemma 3 (1,024-token window, five sliding layers in six) at 16,384, the average cells per layer come to about 4,000 at one slot, 4,900 at two and 6,600 at four, by the formula in [`kv_cells.py`](../../../surfsense_local/backend/modules/llm/fit/kv_cells.py). A model without sliding layers, such as Qwen3, pays nothing extra.
- **Compute buffer.** `SLOTS` sizes the output rows in [`compute_buffers.py`](../../../surfsense_local/backend/modules/llm/fit/compute_buffers.py); it becomes N.
- **Speed.** Replies decoding together each run slower and together run faster. It matters only while they overlap.

The estimate takes N as an input everywhere it assumes 1 today, so the badge the catalog shows and the load the plan makes still agree by construction.

## Why no new measurement

Slots ship on every backend at once, with no per-machine measurement first:

- **What slots change is llama.cpp's own arithmetic.** The two terms above are how llama.cpp sizes the cache and the output rows, and neither depends on the backend. The parts of the estimate that were fitted from measurements, such as the compute buffer's safety margin, do not move with the slot count.
- **A wrong estimate costs speed, not the load.** The preset already passes `fit-target`, so llama.cpp's `--fit` places the layers. If the estimate is low, a few layers land on the CPU and the model runs slower than its badge said, the risk every model already carries.

One test confirms the arithmetic is copied right, which holds on any machine it runs on.

## How many fit at once

The budget, not the slot count, decides. At 16,384, a first turn of 3,500 to 4,800 tokens seats three or four; turns with history seat two or three; a thread whose history fills the window runs alone while the rest wait. Titles are small enough to run beside a long reply. That is the case for four rather than two: the extra slots cost little and are used whenever turns are short.

## Tests

- `plan_load()` with a sliding-window shape on a budget that holds four slots resident at 16,384 returns four at 16,384.
- On a budget that holds only three, then two, then one slot resident at 8,192, it returns 3, 2 and 1, each at the widest window that count holds.
- On a budget where one slot spills at 8,192, it returns four and a `PARTIAL` verdict.
- On Metal it returns four whatever the budget.
- The preset writes `kv-unified = on` with `parallel` above 1 and leaves it out at 1.
- Against the staged llama-server, a sliding-window model loaded at four slots allocates the cache size the estimate computes for four slots, as llama-server reports it at load.
- Against the staged llama-server, two short chat turns decode together and two that overflow the cache run one after the other, with no `runtime_busy`.

## After it ships

- **The window a tight machine gives up.** Whether 8,192 at four slots instead of 16,384 at one shows in answers is for the [chat eval](../chat-eval.md) once it runs. The eval decides whether to revisit the order.
- **Four slots.** Parts 1 and 2 log how often more than two replies overlap. If they rarely do, the ask drops to two.
