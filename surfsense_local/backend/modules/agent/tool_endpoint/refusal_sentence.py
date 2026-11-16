"""Studio's refusal as the sentence a tool result hands the model."""


def refusal_sentence(detail: object) -> str:
    """A refusal the interface translates carries its reason as ``{"message", "code"}``;
    the model reads the message."""
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        detail = detail["message"]
    text = str(detail).strip()
    return text if text.endswith(".") else f"{text}."
