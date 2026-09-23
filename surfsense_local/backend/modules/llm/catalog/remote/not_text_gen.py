"""Text in, text out, and it still cannot answer you.

Embedders and rerankers declare the same modalities as a chat model, so only
the name can refuse them. 93 of 7,846 text-to-text entries.

Not `limit.output`: it holds a vector width for an embedder and a token count
for everything else. Refusing small ones catches 62 models, 61 already caught
here, and the one it adds is a chatbot that answers in 512 tokens.

Terms are added when an audit finds one live, never on speculation. Eight
plausible ones matched nothing across 8,077 entries and were dropped.
"""

__all__ = ["can_answer_in_prose"]

_NOT_TEXT_GEN = (
    "embed",
    "rerank",
    # Families that have only ever shipped embedders and rerankers. The two
    # short ones keep a separator so they cannot land inside another name.
    "voyage",
    "bge",
    "gte-",
    "e5-",
    "mini-lm",
    "mini_lm",
    "mpnet",
)


def can_answer_in_prose(model_id: str) -> bool:
    """Whether a text-to-text model replies in prose rather than in numbers."""
    name = model_id.lower()
    return not any(term in name for term in _NOT_TEXT_GEN)
