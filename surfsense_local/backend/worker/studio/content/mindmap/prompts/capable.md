You organise source documents into mind maps, strictly from what they state.

Task: organise the sources below into a mind map of 6 main branches, two or three levels deep.
$focus
Work in this order:

1. Read every source and note what each one is about and the figures and names it states.
2. Group what you found into 6 themes that hold the material — themes the sources support, not headings you expect to see.
3. Under each theme, hang the specifics: two to five child labels, each a few words. Put a figure or a date in the label where one exists.
4. Check every label against the sources and drop any you cannot point to.

Grounding rules:

- Use only facts the sources state. No outside knowledge, no estimates, no plausible-sounding filler.
- Labels are short — a few words each, never a sentence.
- If a source calls something proposed or pending, label it that way.

Return only JSON, no prose: {"title": str, "nodes": [{"label": str, "children": [{"label": str, "children": [...]}]}]}

Worked example — a different topic in the same shape. Copy the structure, never the content:

{"title": "Leeds-Hull electrification", "nodes": [{"label": "Schedule", "children": [{"label": "Full electrification 2031"}, {"label": "Signalling rescoped"}]}]}

Return only the JSON. Nothing before it, nothing after it.
