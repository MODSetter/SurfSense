---
name: email-drafting
description: Draft an email matching the user's voice, with structured intent and CTA
allowed-tools: search_surfsense_docs
---

# Email drafting

## When to use this skill
"Draft an email to ...", "reply to this thread", "write a follow-up to X". Plain "summarize the email" is **not** in scope — that's a comprehension task.

## Voice
Search the KB for prior emails from the user to similar audiences (same recipient, same topic class). Mirror tone, opening style, sign-off, and length distribution. If there is no precedent, default to: warm, direct, no filler, short paragraphs, one clear ask.

## Required structure
Every draft includes, in this order:

1. **Subject line** — concrete, ≤ 8 words, no clickbait, no `Re:` unless replying.
2. **Opening (1 sentence)** — context the recipient already shares; never restate what they wrote unless the thread is long.
3. **Body** — the actual point in one short paragraph. Bullets only if there are >3 discrete items.
4. **Single explicit CTA** — what you want the recipient to do, with a soft deadline if relevant.
5. **Sign-off** — match the user's prior closing style.

## Always offer alternatives
End your message with: "Want me to make it shorter, more formal, or add a different angle?" — give the user one obvious next step.
