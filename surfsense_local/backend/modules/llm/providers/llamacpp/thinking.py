"""How this runtime is told not to think.

A thinking model emits its whole trace before its first answer token, so a call
with a small `max_tokens` returns nothing. Measured against Qwen3 1.7B at
b11050: a 12 token title request came back `content: ''`, `finish_reason:
length`, and a full `reasoning_content`.

Two mechanisms are sent, because each covers the other's blind spot and both
were measured to work:

- `chat_template_kwargs` is the documented one, listed in the server README as
  a chat completions parameter with this exact example. It is inert on a model
  whose Jinja template never reads `enable_thinking`, which is most of them
  outside the Qwen line.
- `thinking_budget_tokens` is llama.cpp's own end of thinking injection, so it
  holds whatever the template does. It is confirmed upstream but absent from
  the README, which is why it is not relied on alone.

Rejected, both measured:

- `reasoning_budget` as a request field is accepted and ignored. That is the
  failure mode worth naming, because it looks like it worked.
- `--reasoning-budget 0` on the command line applies to the whole router, so it
  would buy a title by removing reasoning from every answer. Worse, setting it
  at all makes the server ignore `thinking_budget_tokens`, whose handler runs
  only while the flag is at its `-1` default. The sidecar must never pass it,
  and a test in the Electron tree holds that.
"""

# Per call, so the answer path keeps the reasoning it actually benefits from.
THINKING_OFF: dict[str, object] = {
    "thinking_budget_tokens": 0,
    "chat_template_kwargs": {"enable_thinking": False},
}
