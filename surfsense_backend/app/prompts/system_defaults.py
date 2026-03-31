SYSTEM_PROMPT_DEFAULTS: list[dict] = [
    {
        "slug": "fix-grammar",
        "name": "Fix grammar",
        "prompt": (
            "Fix the grammar and spelling in the following text."
            " Return only the corrected text, nothing else.\n\n{selection}"
        ),
        "mode": "transform",
    },
    {
        "slug": "make-shorter",
        "name": "Make shorter",
        "prompt": (
            "Make the following text more concise while preserving its meaning."
            " Return only the shortened text, nothing else.\n\n{selection}"
        ),
        "mode": "transform",
    },
    {
        "slug": "translate",
        "name": "Translate",
        "prompt": (
            "Translate the following text to English."
            " If it is already in English, translate it to French."
            " Return only the translation, nothing else.\n\n{selection}"
        ),
        "mode": "transform",
    },
    {
        "slug": "rewrite",
        "name": "Rewrite",
        "prompt": (
            "Rewrite the following text to improve clarity and readability."
            " Return only the rewritten text, nothing else.\n\n{selection}"
        ),
        "mode": "transform",
    },
    {
        "slug": "summarize",
        "name": "Summarize",
        "prompt": (
            "Summarize the following text concisely."
            " Return only the summary, nothing else.\n\n{selection}"
        ),
        "mode": "transform",
    },
    {
        "slug": "explain",
        "name": "Explain",
        "prompt": "Explain the following text in simple terms:\n\n{selection}",
        "mode": "explore",
    },
    {
        "slug": "ask-knowledge-base",
        "name": "Ask my knowledge base",
        "prompt": "Search my knowledge base for information related to:\n\n{selection}",
        "mode": "explore",
    },
    {
        "slug": "look-up-web",
        "name": "Look up on the web",
        "prompt": "Search the web for information about:\n\n{selection}",
        "mode": "explore",
    },
]

SYSTEM_PROMPT_SLUGS: set[str] = {p["slug"] for p in SYSTEM_PROMPT_DEFAULTS}
