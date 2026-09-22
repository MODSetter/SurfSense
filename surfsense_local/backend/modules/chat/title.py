from modules.llm.providers.protocols import Generator
from modules.llm.providers.types import Message

TITLE_PROMPT = """Write a 2-5 word noun-phrase title.
Rewrite the request; do not copy it.
Remove filler such as "tell me", "what's", "please", and "can you".
Return plain text only: no quotes, slashes, Markdown, or explanation.
For greetings and small talk, name the intent instead of repeating the words.

Examples:
"what's there in this chat?" -> Chat Content Overview
"explain the refund policy" -> Refund Policy
"hi bro" -> Casual Greeting

Query: {user_query}
Title:"""

TITLE_MAX_TOKENS = 12
TITLE_MAX_CHARACTERS = 100


async def generate_title(
    generator: Generator, model: str, user_query: str
) -> str | None:
    """Generate and validate a short title without exposing raw model output.

    No timeout of its own. How long a model may take to answer is a fact about
    the runtime, which this module cannot observe: a 30 second budget here
    cancelled a title 9 seconds before a freshly downloaded model finished
    loading. The provider applies one budget until the first token and a tighter
    one between them. What belongs here is the shape of the answer: short,
    single line, and cut off if the model runs on.
    """
    prompt = TITLE_PROMPT.replace(
        "{user_query}", user_query.strip()[:500] or "(message)"
    )
    parts: list[str] = []
    async for delta in generator.chat(
        model,
        [Message("user", prompt)],
        max_tokens=TITLE_MAX_TOKENS,
        temperature=0,
        reasoning=False,
    ):
        parts.append(delta)
        if sum(map(len, parts)) > TITLE_MAX_CHARACTERS + 2:
            return None
    return valid_title("".join(parts))


def valid_title(raw: str) -> str | None:
    """Accept a short single-line title; rendering escapes ordinary punctuation."""
    title = raw.strip().strip("\"'").strip()
    words = title.split()
    if (
        not title
        or len(title) > TITLE_MAX_CHARACTERS
        or "\n" in title
        or not 1 <= len(words) <= 6
    ):
        return None
    return " ".join(words)
