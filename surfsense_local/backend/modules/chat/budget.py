"""How much of a model's context window each part of a turn may spend.

Four named parts share one window: the system prompt, the retrieved excerpts,
the user's question, and the answer. The answer's share is reserved before
anything else claims it, because llama.cpp stops a reply wherever the window
runs out; spending the reserve on history is how a good answer gets cut off
mid-sentence with no error at all. What is left after the fixed parts and the
reserve is what history gets, so a narrower window means a shorter history
rather than a turn that silently exceeds the window (fix from the context-floor
research in docs/architecture/local-models/fit.md: `HISTORY_BUDGET_TOKENS` used
to be a constant with no relationship to `n_ctx`, which was safe only because
the window was always the same 16384 number).

An unknown window (a remote endpoint that does not report `n_ctx`) is not a
narrow one; it is an absent fact, and this module cannot tell whether the
fixed parts fit. The fallback there is today's number, unchanged, rather than
a guess.
"""

# Kept back for the answer before anything else is priced. Never spent on
# history.
ANSWER_RESERVE_TOKENS = 1024

# What a rendered system prompt plus the grounding header cost, at the largest
# tier (frontier.md). Approximate: the exact figure is one `/apply-template`
# call away and this is the estimate until that lands.
SYSTEM_PROMPT_TOKENS = 400

# The retrieval cap already limits chunks to 480 tokens each at up to 5 hits
# (shared/search.py, worker/ingestion/chunking.py); priced here rather than
# measured so the budget holds even before retrieval runs.
EXCERPTS_TOKENS = 2400

# The characters-to-tokens estimate history.py prices turns with when the
# model's own tokenizer is not asked. Dense scripts run richer than this, so
# the cap below is loose for them, never tight.
CHARS_PER_TOKEN = 4

# A pasted question can be long; capped so one turn cannot claim the whole
# window and leave nothing for history or the answer.
QUESTION_TOKENS = 1024

# What one attached image costs the window. The curated vision model, Gemma 3,
# spends a fixed 256; Qwen2.5-VL, downloadable from search, spends ~1,340 at the
# 1024 px cap (modules/chat/images/intake.py). Priced at the larger, so the trim
# drops a turn rather than overflowing the window.
IMAGE_TOKENS = 1400

# What MessageText refuses past, at the wire (modules/chat/schemas.py). One
# global cap rather than one per window: it runs before any model is resolved,
# and the budget prices the question at the same 1,024 for every window.
QUESTION_CHARS = QUESTION_TOKENS * CHARS_PER_TOKEN

# Today's number, kept as the fallback for a window this module cannot see:
# unchanged so a remote model with no reported `n_ctx` behaves exactly as it
# did before this budget existed.
DEFAULT_HISTORY_TOKENS = 3000


def history_budget(n_ctx: int | None) -> int:
    """Room left for prior turns, after the fixed parts and the answer reserve.

    Floors at zero rather than going negative: a window narrower than the
    fixed parts plus the reserve keeps no history at all, which is correct,
    not an error, on the smallest rung this app will ever run at.
    """
    if n_ctx is None:
        return DEFAULT_HISTORY_TOKENS
    spent = (
        SYSTEM_PROMPT_TOKENS + EXCERPTS_TOKENS + QUESTION_TOKENS + ANSWER_RESERVE_TOKENS
    )
    return max(0, n_ctx - spent)


def answer_max_tokens(n_ctx: int | None) -> int | None:
    """`max_tokens` for the answer request, or None to leave the endpoint's
    own default in place.

    None on an unknown window: capping a reply to this app's reserve on an
    endpoint whose real window might be far larger would truncate answers for
    a limit that was never really theirs.
    """
    return ANSWER_RESERVE_TOKENS if n_ctx is not None else None
