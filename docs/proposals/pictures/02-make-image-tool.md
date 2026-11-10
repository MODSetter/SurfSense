# The agent's picture tool

> `surfsense_make_image` gains `shape` and `references`, its description stops steering away from pictures with words or from several pictures, and an edit or a reference that no model can take is drawn from words instead of refused.

Everything else in [`make_image.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/make_image.py) stays: the wait, the three-failure limit, the `image-<id>` names, placing, and the one-title-per-chat refusal.

## New arguments

| Argument | Type | Meaning |
|---|---|---|
| `shape` | `square`, `portrait` or `landscape` | The picture's proportions. Left out, the model's default. |
| `references` | up to 4 picture names | Pictures this chat made, each ready, for the new picture to keep: the same characters and style. Only for a new picture, not with `artifact_id`. |

- **References are checked as placing is** ([`names.py`](../../../surfsense_local/backend/modules/artifacts/drawn_images/names.py)): a name of this chat, ready, a still picture. A picture still being drawn is refused with "Draw it first and wait for it", and none of these refusals is a failed run. Four bounds what one call uploads; the local spike may lower it.
- **A picture with references runs on the model [the rule](01-image-models.md#which-model-handles-a-picture) picks.** When it picks none, the picture is drawn from its prompt alone and the result says so: "Drawn from words alone: the image model cannot take a picture in, so the characters may differ from the reference." Nothing is refused, so the agent never loops on a setting it cannot change.
- **An edit with `artifact_id`** runs as Studio's does ([edits and redraws](01-image-models.md#edits-and-redraws)): a real edit, or a redraw that the result names as one. The tool's refusal for want of an edit model, and its text sending the user to Settings › Image edit, go.
- **The recipe** of a new picture records `shape` and `references` as artifact ids: `{"kind": "image_drawn", "prompt", "shape", "references"}`. Regenerate repeats it with the same references.

## The listing stays fixed

Tool listings are fixed and in one order, so a local model's prompt cache holds from turn to turn ([`offered_tools.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/offered_tools.py)). So `references` is always listed, and what happens without a model is in the result, not in the listing.

## The description

Rewritten, as short as it can be:

- "Only when the user asks for one" stays, and so does "Draw no data chart".
- "Confirm before making more than one" becomes "When a request needs more than one picture, confirm how many once, before the first: each is billed, or takes minutes on their computer."
- "Words that must be exact belong in the document around the picture" becomes "Lettering may come out misspelt: keep words in a picture short, and put text that must be exact in the document around it."
- One line: "For a comic, a storyboard or any set of pictures, load the `surfsense-pictures` skill first."

## The result

Adds, to what it says today:

- **Where it was drawn:** "Drawn on this computer" or "Drawn by <connection name>". The skill draws wordless pages on this computer ([comics](03-comics.md#lettering)).
- **How it was drawn,** when it was not as asked: from words alone, a redraw, or a shape or reference the model did not take.

## Checks

[`test_make_image.py`](../../../surfsense_local/backend/tests/integration/agent/test_make_image.py), against the stand-in painter:

- `shape` reaches the model; references reach it in order; a reference from another chat, a picture still drawing, a fifth reference, and references with `artifact_id` are refused, unbilled.
- With no model that takes pictures, references draw from words and the result says so; an edit redraws and the result says so.
- The result names where the picture was drawn.
- The listing is the same, byte for byte, whatever models are chosen.
