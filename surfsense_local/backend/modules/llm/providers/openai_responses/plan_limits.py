"""What a ChatGPT plan's Responses endpoint refuses, from OpenAI's preview limitations
(developers.openai.com/siwc/token-sharing-open-source/preview-limitations).

The chat's client and the agent's relay both honour it, so it is stated once.
"""

REFUSED_FIELDS = frozenset(
    {
        "background",
        "conversation",
        "max_output_tokens",
        "max_tool_calls",
        "metadata",
        "moderation",
        "multi_agent",
        "previous_response_id",
        "prompt",
        "prompt_cache_retention",
        "safety_identifier",
        "temperature",
        "top_logprobs",
        "top_p",
        "truncation",
        "user",
    }
)
