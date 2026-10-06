from modules.llm.providers.types import Message

# What one image costs the cache, priced as the chat budget prices it.
IMAGE_TOKENS = 1400

# The role and template tokens around every message.
MESSAGE_OVERHEAD_TOKENS = 8

# The answer a request reserves when it states no `max_tokens`.
UNSTATED_OUTPUT_TOKENS = 1024


def request_cost(
    messages: list[Message],
    max_tokens: int | None,
    *,
    budget: int | None,
    slots: int,
) -> int:
    """The tokens a request will hold in the cache: what it sends, and what it
    may write back. Errs high, because undercounting is what overflows the cache.
    """
    prompt = sum(_message_tokens(message) for message in messages)
    if max_tokens is not None and (budget is None or max_tokens < budget):
        return prompt + max_tokens
    allowance = UNSTATED_OUTPUT_TOKENS
    if budget is not None:
        allowance = min(allowance, max(0, budget - prompt))
        # An unstated answer on a short prompt stays within its fair share, so
        # a small cache still seats as many such requests as it has slots.
        share = budget // max(1, slots)
        if prompt < share:
            allowance = min(allowance, share - prompt)
    return prompt + allowance


def _message_tokens(message: Message) -> int:
    return (
        _text_tokens(message.content)
        + IMAGE_TOKENS * len(message.images)
        + MESSAGE_OVERHEAD_TOKENS
    )


def _text_tokens(text: str) -> int:
    """Denser than the chat budget's four characters a token: Latin text runs
    near four, but Chinese, Japanese and Korean run near one a character, and
    pricing those at a quarter would admit requests the cache cannot hold."""
    ascii_chars = sum(1 for char in text if char.isascii())
    return -(-ascii_chars // 3) + (len(text) - ascii_chars)
