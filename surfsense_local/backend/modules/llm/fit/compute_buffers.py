"""The scratch memory a graph needs beyond weights and cache.

Absent from earlier drafts of the estimator entirely, and then present as a
constant, which is nearly as wrong: scratch is sized by the widest thing one
layer computes, so it scales with the model rather than being a fee every model
pays alike. The constant was fitted to a 1.7B and under-stated a 4B by about
70 MiB, which is more than the margin that decided a 12 GB card's top row.

Two parts. A flat term for the activations, the output rows and the safety the
allocator keeps, which is fixed once the model is known. And a term that grows
with the window, for the attention mask and the scratch that goes with it.

> ponytail: the flat term's shape is llama.cpp's own graph, but the safety
> factor and the per token slope are fitted, not derived. Three measured points:
> Qwen3 1.7B on Metal reported 102.24 MiB at 16384 and 222.24 MiB at 40960; a 4B
> on Vulkan reported 143.62 device plus 26.01 host at 16384. The slope is exact
> for the Metal pair, 120 MiB over 24576 tokens.
>
> The two backends disagree about the flat half, and by more than the widths
> explain: the 4B's measured flat is 4.0x the 1.7B's where the modelled widths
> differ by 1.6x. Two models on two backends cannot separate a model effect from
> a backend effect, so this is fitted to cover both rather than to match either,
> and it over-states the 1.7B by a third to do it. Replace the whole term with
> the machine's own residual after a first load, which measures it along with
> everything else that is neither weights nor cache, on the machine that will
> run the model.
"""

from modules.llm.fit.types import ModelShape

# llama-server's defaults, and the `parallel = 1` this app pins in every preset.
UBATCH_TOKENS = 512
SLOTS = 1

# What the allocator keeps beyond the modelled width. Fitted to cover every
# measured point, not derived: the smallest value at which all three land on the
# safe side. At 1.10 the 4B came out at 0.97 of what Vulkan really allocated,
# and under-stating is the direction that ships a confident badge about a model
# that spills.
SAFETY = 1.20

# The context-shaped half: attention mask and its scratch, per token.
PER_TOKEN_BYTES = 5_120

# The line the constant used to be, kept for a header that states no widths at
# all. Wrong in detail, but it is the measured floor for the smallest model and
# is certainly better than pricing scratch at nothing.
_FALLBACK_BASE_BYTES = 23 * 1024**2


def activation_width(shape: ModelShape) -> int:
    """Elements the graph holds live per micro batch token.

    The widest of the three things a layer can be: the attention and residual
    buffers, the dense feed forward, or the experts a router actually reads.
    """
    embedding = shape.embedding_length
    if embedding <= 0:
        return 0

    widths = [12 * embedding]
    if shape.feed_forward_length > 0:
        widths.append(4 * shape.feed_forward_length)

    used = shape.expert_used_count
    expert_width = shape.expert_feed_forward_length or (
        shape.feed_forward_length if shape.expert_count else 0
    )
    if used > 0 and expert_width > 0:
        shared = shape.expert_shared_feed_forward_length
        widths.append(used * (2 * embedding + 3 * expert_width) + 3 * shared)

    return max(widths)


def compute_buffer_bytes(shape: ModelShape, n_ctx: int) -> int:
    """Scratch bytes for a graph over an `n_ctx` window, rounded up.

    Rounding up is the rule the whole estimator runs on: over-stating costs a
    pessimistic badge, under-stating ships a confident badge about a model that
    spills.
    """
    width = activation_width(shape)
    if width <= 0 or shape.n_vocab <= 0:
        return _FALLBACK_BASE_BYTES + PER_TOKEN_BYTES * n_ctx

    activations = width * UBATCH_TOKENS * 4
    outputs = shape.n_vocab * min(UBATCH_TOKENS, SLOTS) * 4
    flat = int((activations + outputs) * SAFETY)
    return flat + PER_TOKEN_BYTES * n_ctx
