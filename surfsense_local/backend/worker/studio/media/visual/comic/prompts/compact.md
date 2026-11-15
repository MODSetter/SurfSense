You plan a short comic from the sources below. Use their facts only.

The comic is a $kind. It has exactly $count $unit(s). Each $unit is one picture: $picture.
$focus

Write:

- "title": the comic's title.
- "style": one sentence: medium, colours, line weight.
- "characters": each character in a few fixed words: face, hair, clothes, colours.
- "pages": exactly $count items. Each has "panels". Each panel has "where" (top, bottom left, wide), "shows" (what is seen in it), and "lines".

$lettering

Rules:

- Only facts from the sources. Do not invent names or numbers.
- Exactly $count $unit(s).
- One moment per panel.

Example of the shape only, not the content:

{"title": "The Lighthouse Cat", "style": "Bold ink lines, flat warm colours.", "characters": "MILO, a small orange tabby cat with a red scarf.", "pages": [{"panels": [{"where": "top", "shows": "A boat in a storm at night.", "lines": ["Caption: The storm came at midnight."]}, {"where": "bottom", "shows": "MILO looks at the dark lamp.", "lines": ["MILO: The light is out!"]}]}]}

Return only the JSON. Nothing before it, nothing after it.
