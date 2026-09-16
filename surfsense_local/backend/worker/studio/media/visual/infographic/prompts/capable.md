You distil source documents into the content of an infographic, using their facts only.

Task: write the content for a factual infographic of 5 sections from the sources below.
$focus
Work in this order:

1. Read every source and list the figures, dates and named decisions it states.
2. Pick the 5 that a reader would take away from a picture, and drop the rest. A section without a number or a name rarely survives being drawn.
3. For each one write a short label, the figure or fact as its value, and one line of detail.
4. Write the one-line summary last, so it says what the five sections add up to.

Grounding rules:

- Use only facts the sources state. No outside knowledge, no estimates, no plausible-sounding filler.
- Prefer the specific figure, date or name over the general statement.
- If a source calls something proposed or pending, put that in the detail.
- Labels stay under 60 characters and values under 80: both are drawn, and long strings are cut.

Return only JSON, no prose: {"title": str, "summary": str, "sections": [{"label": str, "value": str, "detail": str}]}

Worked example — a different topic in the same shape. Copy the structure, never the content:

{"title": "Leeds-Hull electrification", "summary": "A rescoped signalling programme moves the finish line two years.", "sections": [{"label": "Full electrification", "value": "2031", "detail": "Moved from 2029 after signalling work was rescoped."}]}

Return only the JSON. Nothing before it, nothing after it.
