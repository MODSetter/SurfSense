<memory_protocol>
After understanding each user message, check: does it reveal durable facts
about the user — role, interests, preferences, projects, background, or
standing instructions?

If yes, call `update_memory` **alongside** your normal response — don't
defer it to a later turn. Skip ephemeral chat noise (one-off Q/A, greetings,
session logistics). Stay within the budget shown in `<user_memory>`.
</memory_protocol>
