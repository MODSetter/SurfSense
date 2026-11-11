You plan a comic from source documents: a $kind of $count $unit(s), told from their facts only.

Task: plan the comic. Each $unit is one picture: $picture.
$focus
Work in this order:

1. Read every source and pick the story it tells best in $count $unit(s): who, what happens, and how it ends.
2. Write a style line: medium, palette and line weight, in one sentence.
3. Write a character sheet: each character's face, hair, build, clothes and colours in a few fixed words. Every page repeats it word for word, so keep it short and exact.
4. Plan each $unit in reading order: for every panel, where it sits (top, bottom left, wide), what it shows, and its lines.

$lettering

Grounding rules:

- Use only what the sources state. Simplify, but never invent facts, names or figures.
- Plan exactly $count $unit(s), no more.
- A panel shows one moment. Describe what is seen, not what is meant.

Return only JSON, no prose: {"title": str, "style": str, "characters": str, "pages": [{"panels": [{"where": str, "shows": str, "lines": [str]}]}]}

Worked example — a different story in the same shape. Copy the structure, never the content:

{"title": "The Lighthouse Cat", "style": "Bold ink lines, flat warm colours, night-blue sky.", "characters": "MILO, a small orange tabby cat with a white chest, green eyes and a red scarf. NORA, a woman about seventy, short white hair, round glasses, yellow raincoat.", "pages": [{"panels": [{"where": "wide, top", "shows": "A fishing boat tosses on huge waves at night.", "lines": ["Caption: The storm came at midnight."]}, {"where": "bottom left", "shows": "NORA taps the dead lamp.", "lines": ["NORA: The bulb is broken!"]}]}]}

Return only the JSON. Nothing before it, nothing after it.
