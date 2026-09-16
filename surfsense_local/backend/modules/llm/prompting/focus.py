def focus(user_prompt: str | None) -> str:
    """The user's steer as one line a prompt can carry, or nothing at all."""
    return (
        f"Focus on: {user_prompt.strip()}"
        if user_prompt and user_prompt.strip()
        else ""
    )
