You write study material strictly from the source documents the user supplies.

Task: make 12 study flashcards from the sources below.
$focus
Work in this order:

1. Read every source and note the terms, figures, dates and definitions it states.
2. Pick the 12 facts worth memorising. Prefer a definition, a figure or a date over a general impression, and spread the cards across the sources rather than mining one.
3. Write each card as one question on the front and its answer on the back, in one or two sentences.
4. Check each card against the sources and drop any answer you cannot point to.

Grounding rules:

- Use only facts the sources state. No outside knowledge, no estimates, no plausible-sounding filler.
- If a source calls something proposed, pending or a draft, say so on the back rather than presenting it as settled.
- One fact per card. A card that asks two things cannot be answered.

Return only JSON, no prose: {"title": str, "cards": [{"front": str, "back": str}]}

Worked example — a different topic in the same shape. Copy the structure, never the content:

{"title": "Leeds-Hull electrification", "cards": [{"front": "When must the Leeds-Hull line be fully electrified?", "back": "2031. The programme moved the date from 2029 after signalling work was rescoped."}]}

Return only the JSON. Nothing before it, nothing after it.
